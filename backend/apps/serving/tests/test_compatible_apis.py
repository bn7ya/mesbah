from __future__ import annotations

import json
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, cast

import httpx2
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.accounts.repositories import UserRepository
from apps.members.roles import TRAINERS
from apps.models.models import HubModel
from apps.models.repositories import HubModelRepository
from apps.projects.models import Project
from apps.projects.repositories import ProjectRepository
from apps.serving.services import EngineClient
from apps.versions.services import VersionService

if TYPE_CHECKING:
    from django.http import StreamingHttpResponse
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

pytestmark: pytest.MarkDecorator = pytest.mark.filterwarnings(
    "ignore:StreamingHttpResponse must consume asynchronous iterators"
)

PASSWORD: str = "correct-horse-battery-staple"  # noqa: S105
LOADED: dict[str, object] = {"loaded": True, "base": "/models/org-tiny", "adapters": []}


def chunk(delta: dict[str, str], finish: str | None = None) -> str:
    body: dict[str, object] = {"choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
    return f"data: {json.dumps(body)}\n\n"


REPLY: list[str] = [
    chunk({"role": "assistant"}),
    chunk({"reasoning_content": "Greet back."}),
    chunk({"content": "Hello"}),
    chunk({"content": " there"}, finish="stop"),
    'data: {"choices": [], "usage": {"prompt_tokens": 7, "completion_tokens": 2}}\n\n',
    "data: [DONE]\n\n",
]


@pytest.fixture(autouse=True)
def engine() -> Iterator[list[dict[str, Any]]]:
    sent: list[dict[str, Any]] = []

    def status(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=LOADED)

    async def chat(request: httpx2.Request) -> httpx2.Response:
        sent.append(json.loads(request.content))
        return httpx2.Response(200, content="".join(REPLY).encode())

    EngineClient.transport = httpx2.MockTransport(status)
    EngineClient.async_transport = httpx2.MockTransport(chat)
    yield sent
    EngineClient.transport = None
    EngineClient.async_transport = None


@pytest.fixture
def trainer(db: None) -> User:
    users: UserRepository = UserRepository()
    return users.add_to_group(users.create(username="tariq", password=PASSWORD), TRAINERS)


@pytest.fixture
def project(trainer: User) -> Project:
    model: HubModel = HubModelRepository().create(
        repo_id="org/tiny",
        status=HubModel.Status.READY,
        local_path="/models/org-tiny",
        supports_thinking=True,
        parameters=600_000_000,
        model_type="qwen3",
    )
    owner: Project = ProjectRepository().create(name="Tiny", slug="tiny", base_model=model)
    VersionService(trainer).create_root(owner)
    return owner


@pytest.fixture
def key(trainer: User) -> str:
    api: APIClient = APIClient()
    api.force_login(trainer)
    created: ApiResponse = api.post("/api/serving/keys/", {"name": "laptop"}, format="json")
    secret: str = created.json()["key"]
    return secret


def client(key: str | None) -> APIClient:
    api: APIClient = APIClient()
    if key is not None:
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {key}")
    return api


def lines(response: StreamingHttpResponse) -> list[str]:
    return [line for line in b"".join(response).decode().split("\n") if line]


@pytest.mark.django_db
def test_a_key_is_shown_once_and_kept_as_a_digest(trainer: User, key: str) -> None:
    api: APIClient = APIClient()
    api.force_login(trainer)

    listed: dict[str, Any] = api.get("/api/serving/keys/").json()["results"][0]

    assert key.startswith("msb_")
    assert "key" not in listed
    assert key.startswith(listed["prefix"])
    assert listed["owner"] == "tariq"


@pytest.mark.django_db
def test_without_a_key_the_answer_is_an_openai_error(project: Project) -> None:
    response: ApiResponse = client(None).get("/v1/models")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"
    assert response["WWW-Authenticate"].startswith("Bearer")


@pytest.mark.django_db
def test_models_are_projects_and_their_versions(project: Project, key: str) -> None:
    names: list[str] = [row["id"] for row in client(key).get("/v1/models").json()["data"]]

    assert names == ["tiny", "tiny:v0"]


@pytest.mark.django_db
def test_a_chat_completion_with_its_thinking(
    project: Project, key: str, engine: list[dict[str, Any]]
) -> None:
    response: ApiResponse = client(key).post(
        "/v1/chat/completions",
        {"model": "tiny", "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 9},
        format="json",
    )

    body: dict[str, Any] = response.json()
    assert body["object"] == "chat.completion"
    assert body["model"] == "tiny"
    assert body["choices"][0]["message"] == {
        "role": "assistant",
        "content": "Hello there",
        "reasoning_content": "Greet back.",
    }
    assert body["usage"] == {"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 9}
    assert engine[-1]["model"] == "base"
    assert engine[-1]["max_tokens"] == 9
    assert engine[-1]["chat_template_kwargs"] == {"enable_thinking": True}


@pytest.mark.django_db
def test_a_streamed_chat_completion(project: Project, key: str) -> None:
    response: StreamingHttpResponse = cast(
        "StreamingHttpResponse",
        client(key).post(
            "/v1/chat/completions",
            {
                "model": "tiny:v0",
                "messages": [{"role": "user", "content": [{"type": "text", "text": "Hi"}]}],
                "stream": True,
                "stream_options": {"include_usage": True},
            },
            format="json",
        ),
    )

    events: list[str] = lines(response)
    assert events[-1] == "data: [DONE]"
    chunks: list[dict[str, Any]] = [json.loads(event[6:]) for event in events[:-1]]
    deltas: list[dict[str, str]] = [c["choices"][0]["delta"] for c in chunks if c["choices"]]
    assert {"reasoning_content": "Greet back."} in deltas
    assert "".join(delta.get("content", "") for delta in deltas) == "Hello there"
    assert chunks[-1]["usage"]["total_tokens"] == 9


@pytest.mark.django_db
def test_an_unknown_model_is_named(project: Project, key: str) -> None:
    response: ApiResponse = client(key).post(
        "/v1/chat/completions",
        {"model": "tiny:v7", "messages": [{"role": "user", "content": "Hi"}]},
        format="json",
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "model_not_found"


@pytest.mark.django_db
def test_ollama_chat_streams_lines_of_json(project: Project, key: str) -> None:
    response: StreamingHttpResponse = cast(
        "StreamingHttpResponse",
        client(key).post(
            "/ollama/api/chat",
            {"model": "tiny:latest", "messages": [{"role": "user", "content": "Hi"}]},
            format="json",
        ),
    )

    parts: list[dict[str, Any]] = [json.loads(line) for line in lines(response)]
    assert response["Content-Type"] == "application/x-ndjson"
    assert "".join(part["message"]["content"] for part in parts) == "Hello there"
    assert any(part["message"].get("thinking") == "Greet back." for part in parts)
    assert parts[-1]["done"] is True
    assert parts[-1]["eval_count"] == 2


@pytest.mark.django_db
def test_ollama_generate_in_one_answer(project: Project, key: str) -> None:
    body: dict[str, Any] = (
        client(key)
        .post(
            "/ollama/api/generate",
            {"model": "tiny", "prompt": "Hi", "stream": False, "think": False},
            format="json",
        )
        .json()
    )

    assert body["response"] == "Hello there"
    assert body["done"] is True


@pytest.mark.django_db
def test_ollama_lists_and_shows_models(project: Project, key: str) -> None:
    tags: dict[str, Any] = client(key).get("/ollama/api/tags").json()
    shown: dict[str, Any] = client(key).post("/ollama/api/show", {"model": "tiny"}).json()
    version: dict[str, Any] = client(None).get("/ollama/api/version").json()

    assert [model["name"] for model in tags["models"]] == ["tiny", "tiny:v0"]
    assert tags["models"][0]["details"]["parameter_size"] == "0.6B"
    assert shown["capabilities"] == ["completion", "thinking"]
    assert "version" in version


@pytest.mark.django_db
def test_a_revoked_key_stops_working(trainer: User, project: Project, key: str) -> None:
    api: APIClient = APIClient()
    api.force_login(trainer)
    key_id: str = api.get("/api/serving/keys/").json()["results"][0]["id"]

    api.delete(f"/api/serving/keys/{key_id}/")

    assert client(key).get("/v1/models").status_code == 401
