from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from typing import Any

from asgiref.sync import sync_to_async
from django.contrib.auth.models import AnonymousUser, User
from django.db import transaction
from rest_framework.exceptions import APIException, NotFound

from apps.chat.models import Conversation, Message
from apps.chat.repositories import ConversationRepository, MessageRepository
from apps.chat.services.conversation_service import describe_message
from apps.chat.services.errors import NoVersion
from apps.serving.services import DeploymentService, EngineClient, EngineError, Piece, Target
from apps.versions.models import ModelVersion

KEEPALIVE_SECONDS: float = 10.0
TITLE_LENGTH: int = 60

type Render = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class Turn:
    conversation: Conversation
    asked: Message
    reply: Message
    version: ModelVersion
    body: dict[str, object]
    started: float = field(default_factory=time.monotonic)


@dataclass
class Draft:
    content: list[str] = field(default_factory=list)
    thinking: list[str] = field(default_factory=list)
    finish_reason: str = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    engine_name: str = ""


@dataclass(frozen=True)
class Failure:
    code: str
    message: str


class Finished:
    pass


type Item = Piece | Target | Failure | Finished


class ReplyService:
    def __init__(self, user: User | AnonymousUser) -> None:
        self.user: User | AnonymousUser = user
        self.conversations: ConversationRepository = ConversationRepository()
        self.messages: MessageRepository = MessageRepository()
        self.deployments: DeploymentService = DeploymentService(user)

    @transaction.atomic
    def begin(self, conversation_id: str, content: str) -> Turn:
        conversation: Conversation | None = self.conversations.locked(conversation_id)
        if conversation is None:
            raise NotFound
        version: ModelVersion | None = conversation.version or conversation.project.active_version
        if version is None:
            raise NoVersion
        position: int = self.messages.next_position(conversation)
        asked: Message = self.messages.create(
            created_by=self._actor(),
            conversation=conversation,
            position=position,
            role=Message.Role.USER,
            content=content,
        )
        reply: Message = self.messages.create(
            created_by=self._actor(),
            conversation=conversation,
            position=position + 1,
            role=Message.Role.ASSISTANT,
            status=Message.Status.STREAMING,
            version=version,
        )
        changes: dict[str, Any] = {} if conversation.title else {"title": _title(content)}
        self.conversations.update(conversation, **changes)
        return Turn(conversation, asked, reply, version, self._body(conversation, reply))

    async def stream(self, turn: Turn, render: Render) -> AsyncGenerator[str]:
        yield _event(
            "start",
            {
                "asked": render(describe_message(turn.asked)),
                "reply": render(describe_message(turn.reply)),
            },
        )
        queue: asyncio.Queue[Item] = asyncio.Queue()
        pump: asyncio.Task[None] = asyncio.create_task(self._pump(turn, queue))
        draft: Draft = Draft()
        failure: Failure | None = None
        try:
            while True:
                try:
                    item: Item = await asyncio.wait_for(queue.get(), KEEPALIVE_SECONDS)
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if isinstance(item, Finished):
                    break
                if isinstance(item, Failure):
                    failure = item
                    break
                if isinstance(item, Target):
                    draft.engine_name = item.engine_name
                    yield _event("ready", {"engine": item.engine_name})
                    continue
                event: str | None = _apply(draft, item)
                if event is not None:
                    yield _event(event, {"text": item.text})
        except (asyncio.CancelledError, GeneratorExit):
            pump.cancel()
            await asyncio.shield(sync_to_async(self._finish)(turn, draft, None, stopped=True))
            raise
        finally:
            pump.cancel()
        saved: dict[str, Any] = await sync_to_async(self._finish)(turn, draft, failure)
        if failure is None:
            yield _event("done", {"reply": render(saved)})
        else:
            yield _event(
                "error",
                {"code": failure.code, "message": failure.message, "reply": render(saved)},
            )

    async def _pump(self, turn: Turn, queue: asyncio.Queue[Item]) -> None:
        try:
            target: Target = await sync_to_async(self.deployments.target)(
                turn.version, turn.conversation.engine
            )
            await queue.put(target)
            client: EngineClient = EngineClient(target.endpoint)
            async for piece in client.stream_chat({**turn.body, "model": target.model}):
                await queue.put(piece)
        except EngineError as error:
            await queue.put(Failure(error.code, error.detail))
        except APIException as error:
            await queue.put(Failure(str(error.default_code), str(error.detail)))
        else:
            await queue.put(Finished())

    def _finish(
        self, turn: Turn, draft: Draft, failure: Failure | None, *, stopped: bool = False
    ) -> dict[str, Any]:
        status: Message.Status = Message.Status.COMPLETE
        if stopped:
            status = Message.Status.STOPPED
        elif failure is not None:
            status = Message.Status.FAILED
        reply: Message = self.messages.update(
            turn.reply,
            status=status,
            content="".join(draft.content),
            thinking="".join(draft.thinking).strip(),
            engine_name=draft.engine_name[:120],
            finish_reason=draft.finish_reason[:20],
            error_code="" if failure is None else failure.code[:40],
            tokens_prompt=draft.prompt_tokens,
            tokens_completion=draft.completion_tokens,
            latency_ms=int((time.monotonic() - turn.started) * 1000),
        )
        self.conversations.update(turn.conversation)
        return describe_message(reply)

    def _body(self, conversation: Conversation, reply: Message) -> dict[str, object]:
        system: str = conversation.system_prompt or conversation.project.system_prompt
        messages: list[dict[str, str]] = [{"role": "system", "content": system}] if system else []
        for message in self.messages.history(conversation):
            if message.pk == reply.pk or message.role == Message.Role.SYSTEM:
                continue
            entry: dict[str, str] = {"role": message.role, "content": message.content}
            if message.role == Message.Role.ASSISTANT and message.thinking:
                entry["reasoning_content"] = message.thinking
            messages.append(entry)
        generation: dict[str, Any] = {
            **conversation.project.generation,
            **(conversation.generation or {}),
        }
        return {
            "messages": messages,
            "temperature": generation.get("temperature"),
            "top_p": generation.get("top_p"),
            "max_tokens": generation.get("max_tokens"),
            "chat_template_kwargs": {"enable_thinking": conversation.thinking},
        }

    def _actor(self) -> User | None:
        return self.user if isinstance(self.user, User) else None


def _apply(draft: Draft, piece: Piece) -> str | None:
    if piece.kind == "thinking":
        draft.thinking.append(piece.text)
        return "thinking"
    if piece.kind == "content":
        draft.content.append(piece.text)
        return "content"
    if piece.kind == "finish":
        draft.finish_reason = piece.text
    else:
        draft.prompt_tokens = piece.prompt_tokens
        draft.completion_tokens = piece.completion_tokens
    return None


def _event(name: str, data: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _title(content: str) -> str:
    line: str = " ".join(content.split())
    return line if len(line) <= TITLE_LENGTH else f"{line[: TITLE_LENGTH - 1]}…"
