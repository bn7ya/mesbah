from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from django.db.models import QuerySet

from apps.chat.models import Message
from apps.chat.repositories import MessageRepository


class ExampleService:
    def __init__(self) -> None:
        self.messages: MessageRepository = MessageRepository()

    def corrections(self, project_id: str) -> QuerySet[Message]:
        return self.messages.approved_replies(project_id)

    def example(self, reply: Message) -> dict[str, Any]:
        system: str = reply.conversation.system_prompt or reply.conversation.project.system_prompt
        turns: list[dict[str, str]] = [{"role": "system", "content": system}] if system else []
        for message in self.messages.before(reply):
            if message.role != Message.Role.SYSTEM:
                turns.append(_turn(message))
        turns.append(_turn(reply))
        return {"messages": turns}

    def describe(self, reply: Message) -> dict[str, Any]:
        return {
            "id": reply.pk,
            "conversation": {"id": reply.conversation_id, "title": reply.conversation.title},
            "messages": self.example(reply)["messages"],
            "corrected": reply.content_edited_at is not None,
            "thinking_corrected": reply.thinking_edited_at is not None,
            "approved_by": None if reply.approved_by is None else reply.approved_by.get_username(),
            "updated_at": reply.updated_at,
        }

    def write(self, project_id: str, path: Path) -> int:
        count: int = 0
        with path.open("w", encoding="utf-8") as handle:
            for row in self._rows(project_id):
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                count += 1
        return count

    def _rows(self, project_id: str) -> Iterator[dict[str, Any]]:
        for reply in self.corrections(project_id).iterator():
            yield self.example(reply)


def _turn(message: Message) -> dict[str, str]:
    turn: dict[str, str] = {"role": message.role, "content": message.content}
    if message.role == Message.Role.ASSISTANT and message.thinking:
        turn["thinking"] = message.thinking
    return turn
