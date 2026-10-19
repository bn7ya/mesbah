from __future__ import annotations

import socket
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import httpx2
import ollama
import openai
import pytest
import uvicorn
from django.contrib.auth.models import User
from django.core.handlers.wsgi import WSGIHandler
from django.core.signals import request_finished, request_started
from django.db import close_old_connections
from openai.types.chat import ChatCompletion, ChatCompletionChunk, ChatCompletionMessageParam
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from apps.accounts.repositories import UserRepository
from apps.members.roles import TRAINERS
from apps.models.models import HubModel
from apps.models.repositories import HubModelRepository
from apps.projects.models import Project
from apps.projects.repositories import ProjectRepository
from apps.versions.models import ModelVersion
from apps.versions.repositories import VersionRepository
from apps.versions.services import VersionService
from contracts import Contract
from contracts.shapes import events
from mesbah.runtime.app import create_app
from mesbah.runtime.fake import FakeEngine

pytestmark: list[pytest.MarkDecorator] = [
    pytest.mark.contract,
    pytest.mark.filterwarnings("ignore:StreamingHttpResponse must consume asynchronous iterators"),
]

PASSWORD: str = "correct-horse-battery-staple"  # noqa: S105
HELLO: list[ChatCompletionMessageParam] = [{"role": "user", "content": "Hello"}]
FAIL: list[ChatCompletionMessageParam] = [{"role": "user", "content": "Please [fail]"}]


@dataclass
class Calls:
    recorded: dict[str, object] = field(default_factory=dict)
    label: str = ""

    def record(self, request: str, status: int, content_type: str, body: bytes) -> str:
        kind: str = content_type.split(";")[0].strip()
        self.recorded[self.label] = {
            "request": request,
            "status": status,
            "content_type": kind,
            "body": events(kind, body),
        }
        return kind


@dataclass
class OpenAIRecording(httpx2.BaseTransport):
    inner: httpx2.BaseTransport
    calls: Calls

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        response: httpx2.Response = self.inner.handle_request(request)
        body: bytes = response.read()
        kind: str = self.calls.record(
            f"{request.method} {request.url.path}",
            response.status_code,
            response.headers.get("content-type", ""),
            body,
        )
        return httpx2.Response(
            response.status_code, headers={"content-type": kind}, content=body, request=request
        )


@dataclass
class OllamaRecording(httpx.BaseTransport):
    inner: httpx.BaseTransport
    calls: Calls

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response: httpx.Response = self.inner.handle_request(request)
        body: bytes = response.read()
        kind: str = self.calls.record(
            f"{request.method} {request.url.path}",
            response.status_code,
            response.headers.get("content-type", ""),
            body,
        )
        return httpx.Response(
            response.status_code, headers={"content-type": kind}, content=body, request=request
        )


@pytest.fixture
def engine_url() -> Iterator[str]:
    listening: socket.socket = socket.socket()
    listening.bind(("127.0.0.1", 0))
    port: int = listening.getsockname()[1]
    server: uvicorn.Server = uvicorn.Server(
        uvicorn.Config(create_app(FakeEngine(delay=0), None), log_level="warning")
    )
    thread: threading.Thread = threading.Thread(
        target=server.run, kwargs={"sockets": [listening]}, daemon=True
    )
    thread.start()
    while not server.started:
        thread.join(0.01)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join()


@pytest.fixture
def django_app(settings: Settings, engine_url: str, key: str) -> Iterator[WSGIHandler]:
    settings.MESBAH_RUNTIME_URL = engine_url
    settings.MESBAH_RUNTIME_TOKEN = ""
    # As Django's test client does, and after `key` used it: a request must not close the
    # test's own connection.
    request_started.disconnect(close_old_connections)
    request_finished.disconnect(close_old_connections)
    yield WSGIHandler()
    request_started.connect(close_old_connections)
    request_finished.connect(close_old_connections)


@pytest.fixture
def key(db: None, tmp_path: Path) -> str:
    users: UserRepository = UserRepository()
    trainer: User = users.add_to_group(users.create(username="tariq", password=PASSWORD), TRAINERS)
    base: Path = tmp_path / "base"
    adapter: Path = tmp_path / "v1"
    base.mkdir()
    adapter.mkdir()
    (adapter / "adapter_config.json").write_text("{}")
    model: HubModel = HubModelRepository().create(
        repo_id="org/tiny",
        status=HubModel.Status.READY,
        local_path=str(base),
        supports_thinking=True,
        parameters=600_000_000,
        model_type="qwen3",
    )
    project: Project = ProjectRepository().create(name="Tiny", slug="tiny", base_model=model)
    root: ModelVersion = VersionService(trainer).create_root(project)
    VersionRepository().create(
        project=project,
        parent=root,
        number=1,
        kind=ModelVersion.Kind.LORA,
        storage_dir=str(adapter),
    )
    api: APIClient = APIClient()
    api.force_login(trainer)
    secret: str = api.post("/api/serving/keys/", {"name": "contract"}, format="json").json()["key"]
    return secret


def openai_calls(django_app: WSGIHandler, key: str) -> Calls:
    calls: Calls = Calls()
    transport: OpenAIRecording = OpenAIRecording(httpx2.WSGITransport(app=django_app), calls)
    client: openai.OpenAI = openai.OpenAI(
        base_url="http://testserver/v1", api_key=key, http_client=httpx2.Client(transport=transport)
    )
    calls.label = "models"
    listed: list[str] = [model.id for model in client.models.list()]
    assert listed[:3] == ["tiny", "tiny:v0", "tiny:v1"]

    calls.label = "chat"
    whole: ChatCompletion = client.chat.completions.create(
        model="tiny", messages=HELLO, max_tokens=64
    )
    assert whole.choices[0].message.content == "Reply from base: Hello"
    assert whole.choices[0].finish_reason == "stop"
    assert whole.usage is not None
    assert whole.usage.total_tokens == whole.usage.prompt_tokens + whole.usage.completion_tokens

    calls.label = "chat streamed"
    chunks: list[ChatCompletionChunk] = list(
        client.chat.completions.create(
            model="tiny:v1",
            messages=HELLO,
            stream=True,
            stream_options={"include_usage": True},
        )
    )
    assert len({chunk.id for chunk in chunks}) == 1
    assert all(chunk.created > 0 for chunk in chunks)
    text: str = "".join(chunk.choices[0].delta.content or "" for chunk in chunks if chunk.choices)
    assert text.startswith("Reply from ")

    calls.label = "chat failed midway"
    with pytest.raises(openai.APIError):
        list(client.chat.completions.create(model="tiny", messages=FAIL, stream=True))

    calls.label = "unknown model"
    with pytest.raises(openai.NotFoundError):
        client.chat.completions.create(model="tiny:v9", messages=HELLO)

    calls.label = "invalid key"
    stranger: openai.OpenAI = openai.OpenAI(
        base_url="http://testserver/v1",
        api_key="msb_not-a-key",
        http_client=httpx2.Client(transport=transport),
    )
    with pytest.raises(openai.AuthenticationError):
        stranger.models.list()
    return calls


def ollama_calls(django_app: WSGIHandler, key: str) -> Calls:
    calls: Calls = Calls()
    transport: OllamaRecording = OllamaRecording(httpx.WSGITransport(app=django_app), calls)
    client: ollama.Client = ollama.Client(
        host="http://testserver/ollama",
        headers={"Authorization": f"Bearer {key}"},
        transport=transport,
    )
    calls.label = "tags"
    names: list[str | None] = [model.model for model in client.list().models]
    assert names[:3] == ["tiny", "tiny:v0", "tiny:v1"]

    calls.label = "show"
    assert client.show("tiny").modified_at is not None

    calls.label = "chat"
    answer: ollama.ChatResponse = client.chat(model="tiny", messages=HELLO, stream=False)
    assert answer.done is True
    assert answer.message.content == "Reply from base: Hello"

    calls.label = "chat streamed"
    parts: list[ollama.ChatResponse] = list(
        client.chat(model="tiny:v1", messages=HELLO, stream=True)
    )
    assert parts[-1].done is True

    calls.label = "generate streamed"
    generated: list[ollama.GenerateResponse] = list(
        client.generate(model="tiny", prompt="Hello", stream=True)
    )
    assert generated[-1].done is True

    calls.label = "chat failed midway"
    with pytest.raises(ollama.ResponseError):
        list(client.chat(model="tiny", messages=FAIL, stream=True))

    calls.label = "version"
    plain: httpx.Client = httpx.Client(transport=transport, base_url="http://testserver")
    assert isinstance(plain.get("/ollama/api/version").json()["version"], str)
    return calls


@pytest.mark.django_db
def test_v1_and_ollama_answer_as_their_clients_expect(
    contract: Contract, django_app: WSGIHandler, key: str
) -> None:
    openai_recorded: Calls = openai_calls(django_app, key)
    ollama_recorded: Calls = ollama_calls(django_app, key)

    contract.check(
        "compat.json", {"openai": openai_recorded.recorded, "ollama": ollama_recorded.recorded}
    )
