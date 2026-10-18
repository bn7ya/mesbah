from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from django.contrib.auth.models import AnonymousUser, User
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.chat.models import Message
from apps.chat.repositories import MessageRepository
from apps.chat.services.conversation_service import describe_message
from apps.chat.services.errors import EmptyReply, MessageChanged, NotEditable

type Part = Literal["content", "thinking"]


class MessageService:
    def __init__(self, user: User | AnonymousUser) -> None:
        self.user: User | AnonymousUser = user
        self.messages: MessageRepository = MessageRepository()

    def find(self, message_id: str) -> Message:
        message: Message | None = self.messages.find(message_id)
        if message is None:
            raise NotFound
        return message

    @transaction.atomic
    def edit(
        self,
        message_id: str,
        *,
        seen: datetime,
        content: str | None = None,
        thinking: str | None = None,
        include_in_training: bool | None = None,
    ) -> dict[str, Any]:
        message: Message = self._editable(message_id, seen)
        changes: dict[str, Any] = {}
        now: datetime = timezone.now()
        if content is not None and content != message.content:
            changes.update(self._replace(message, "content", content, now))
        if thinking is not None and thinking.strip() != message.thinking:
            changes.update(self._replace(message, "thinking", thinking.strip(), now))
        if changes:
            changes.update(edited_by=self._actor(), approved=True, approved_by=self._actor())
        if include_in_training is not None:
            changes["include_in_training"] = include_in_training
        if changes:
            message = self.messages.update(message, **changes)
        return describe_message(message)

    @transaction.atomic
    def restore(self, message_id: str, part: Part, *, seen: datetime) -> dict[str, Any]:
        message: Message = self._editable(message_id, seen)
        if getattr(message, f"{part}_edited_at") is None:
            return describe_message(message)
        message = self.messages.update(
            message,
            **{
                part: getattr(message, f"original_{part}"),
                f"original_{part}": "",
                f"{part}_edited_at": None,
            },
        )
        return describe_message(message)

    @transaction.atomic
    def approve(self, message_id: str, approved: bool) -> dict[str, Any]:
        message: Message = self._assistant(message_id)
        if approved and message.is_empty:
            raise EmptyReply
        message = self.messages.update(
            message, approved=approved, approved_by=self._actor() if approved else None
        )
        return describe_message(message)

    def _replace(self, message: Message, part: Part, value: str, now: datetime) -> dict[str, Any]:
        changes: dict[str, Any] = {part: value, f"{part}_edited_at": now}
        if getattr(message, f"{part}_edited_at") is None:
            changes[f"original_{part}"] = getattr(message, part)
        elif value == getattr(message, f"original_{part}"):
            changes.update({f"original_{part}": "", f"{part}_edited_at": None})
        return changes

    def _editable(self, message_id: str, seen: datetime) -> Message:
        message: Message = self._assistant(message_id)
        if message.updated_at != seen:
            raise MessageChanged
        return message

    def _assistant(self, message_id: str) -> Message:
        message: Message | None = self.messages.locked(message_id)
        if message is None:
            raise NotFound
        if message.role != Message.Role.ASSISTANT or message.status == Message.Status.STREAMING:
            raise NotEditable
        return message

    def _actor(self) -> User | None:
        return self.user if isinstance(self.user, User) else None
