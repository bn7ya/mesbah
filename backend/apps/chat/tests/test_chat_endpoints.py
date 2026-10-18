from __future__ import annotations

import json
from collections.abc import AsyncGenerator, Iterator
from typing import TYPE_CHECKING, Any, cast

import httpx2
import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.accounts.repositories import UserRepository
from apps.chat.models import Message
from apps.chat.repositories import MessageRepository
from apps.chat.serializers import MessageSerializer
from apps.chat.services import ReplyService
from apps.chat.services.reply_service import Turn
from apps.members.roles import REVIEWERS, VIEWERS
from apps.models.models import HubModel
from apps.models.repositories import HubModelRepository
from apps.serving.services import EngineClient

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


class FakeEngine:
    def __init__(self, lines: list[str]) -> None:
        self.lines: list[str] = lines
        self.requests: list[dict[str, Any]] = []

    def status(self, request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=LOADED)

    async def chat(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(json.loads(request.content))
        return httpx2.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content="".join(self.lines).encode(),
        )


@pytest.fixture
def engine() -> Iterator[FakeEngine]:
    fake: FakeEngine = FakeEngine(
        [
            chunk({"role": "assistant"}),
            chunk({"reasoning_content": "The user greets. "}),
            chunk({"reasoning_content": "Greet back."}),
            chunk({"content": "Hello"}),
            chunk({"content": " there"}, finish="stop"),
            'data: {"choices": [], "usage": {"prompt_tokens": 9, "completion_tokens": 4}}\n\n',
            "data: [DONE]\n\n",
        ]
    )
    EngineClient.transport = httpx2.MockTransport(fake.status)
    EngineClient.async_transport = httpx2.MockTransport(fake.chat)
    yield fake
    EngineClient.transport = None
    EngineClient.async_transport = None


@pytest.fixture
def reviewer(db: None) -> User:
    users: UserRepository = UserRepository()
    return users.add_to_group(users.create(username="rana", password=PASSWORD), REVIEWERS)


@pytest.fixture
def client(reviewer: User) -> APIClient:
    api: APIClient = APIClient()
    api.force_login(reviewer)
    return api


@pytest.fixture
def conversation(client: APIClient, reviewer: User) -> dict[str, Any]:
    model: HubModel = HubModelRepository().create(
        repo_id="org/tiny",
        status=HubModel.Status.READY,
        local_path="/models/org-tiny",
        supports_thinking=True,
    )
    owner: User = UserRepository().create(username="admin", password=PASSWORD)
    owner.is_superuser = True
    owner.save()
    admin: APIClient = APIClient()
    admin.force_login(owner)
    project: dict[str, Any] = admin.post(
        "/api/projects/",
        {"name": "Tiny", "base_model": str(model.pk), "system_prompt": "Be brief."},
        format="json",
    ).json()
    created: ApiResponse = client.post("/api/chat/", {"project": project["id"]}, format="json")
    body: dict[str, Any] = created.json()
    return body


def events(response: StreamingHttpResponse) -> list[tuple[str, dict[str, Any]]]:
    text: str = b"".join(response).decode()
    parsed: list[tuple[str, dict[str, Any]]] = []
    for block in text.split("\n\n"):
        lines: list[str] = [line for line in block.splitlines() if not line.startswith(":")]
        if not lines:
            continue
        name: str = lines[0].removeprefix("event: ")
        parsed.append((name, json.loads(lines[1].removeprefix("data: "))))
    return parsed


def ask(client: APIClient, conversation_id: str, content: str) -> StreamingHttpResponse:
    response: object = client.post(
        f"/api/chat/{conversation_id}/reply/", {"content": content}, format="json"
    )
    return cast("StreamingHttpResponse", response)


@pytest.mark.django_db
def test_a_reply_streams_thinking_then_content(
    client: APIClient, conversation: dict[str, Any], engine: FakeEngine
) -> None:
    response: StreamingHttpResponse = ask(client, conversation["id"], "Hi")

    assert response["Content-Type"] == "text/event-stream"
    stream: list[tuple[str, dict[str, Any]]] = events(response)
    names: list[str] = [name for name, _ in stream]
    assert names == ["start", "ready", "thinking", "thinking", "content", "content", "done"]
    reply: dict[str, Any] = stream[-1][1]["reply"]
    assert reply["status"] == "complete"
    assert reply["content"] == "Hello there"
    assert reply["thinking"] == "The user greets. Greet back."
    assert reply["tokens_completion"] == 4
    assert reply["version"]["name"] == "base"


@pytest.mark.django_db
def test_the_engine_gets_the_prompt_and_the_history(
    client: APIClient, conversation: dict[str, Any], engine: FakeEngine
) -> None:
    events(ask(client, conversation["id"], "Hi"))
    events(ask(client, conversation["id"], "And again"))

    sent: dict[str, Any] = engine.requests[-1]
    assert sent["model"] == "base"
    assert sent["stream"] is True
    assert sent["chat_template_kwargs"] == {"enable_thinking": True}
    assert [message["role"] for message in sent["messages"]] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert sent["messages"][2]["reasoning_content"] == "The user greets. Greet back."


@pytest.mark.django_db
def test_a_conversation_keeps_its_messages_and_takes_a_title(
    client: APIClient, conversation: dict[str, Any], engine: FakeEngine
) -> None:
    events(ask(client, conversation["id"], "What is a LoRA?"))

    messages: list[dict[str, Any]] = client.get(f"/api/chat/{conversation['id']}/messages/").json()[
        "results"
    ]
    assert [(message["role"], message["status"]) for message in messages] == [
        ("user", "complete"),
        ("assistant", "complete"),
    ]
    assert client.get(f"/api/chat/{conversation['id']}/").json()["title"] == "What is a LoRA?"


@pytest.mark.django_db
def test_a_stopped_engine_ends_the_stream_with_an_error(
    client: APIClient, conversation: dict[str, Any]
) -> None:
    def refuse(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("refused", request=request)

    EngineClient.transport = httpx2.MockTransport(refuse)
    try:
        stream: list[tuple[str, dict[str, Any]]] = events(ask(client, conversation["id"], "Hi"))
    finally:
        EngineClient.transport = None

    name, data = stream[-1]
    assert name == "error"
    assert data["code"] == "engine_unreachable"
    assert data["reply"]["status"] == "failed"


@pytest.mark.django_db
def test_closing_the_stream_keeps_what_arrived(
    reviewer: User, conversation: dict[str, Any], engine: FakeEngine
) -> None:
    service: ReplyService = ReplyService(reviewer)
    turn: Turn = service.begin(conversation["id"], "Hi")

    def render(message: dict[str, Any]) -> dict[str, Any]:
        return dict(MessageSerializer(message).data)

    async def read_until_the_first_words() -> None:
        stream: AsyncGenerator[str] = service.stream(turn, render)
        for _ in range(5):
            await anext(stream)
        await stream.aclose()

    async_to_sync(read_until_the_first_words)()

    saved: Message | None = MessageRepository().find(turn.reply.pk)
    assert saved is not None
    assert saved.status == Message.Status.STOPPED
    assert saved.content == "Hello"
    assert saved.thinking == "The user greets. Greet back."


@pytest.mark.django_db
def test_a_blank_message_is_refused(client: APIClient, conversation: dict[str, Any]) -> None:
    response: ApiResponse = client.post(
        f"/api/chat/{conversation['id']}/reply/", {"content": "   "}, format="json"
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_viewers_read_but_cannot_chat(conversation: dict[str, Any]) -> None:
    users: UserRepository = UserRepository()
    viewer: User = users.add_to_group(users.create(username="noor", password=PASSWORD), VIEWERS)
    api: APIClient = APIClient()
    api.force_login(viewer)

    assert api.get("/api/chat/", {"project": conversation["project"]}).status_code == 200
    reply: ApiResponse = api.post(
        f"/api/chat/{conversation['id']}/reply/", {"content": "Hi"}, format="json"
    )
    assert reply.status_code == 403
