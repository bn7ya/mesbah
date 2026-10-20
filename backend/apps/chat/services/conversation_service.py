from __future__ import annotations

from typing import Any

from django.contrib.auth.models import AnonymousUser, User
from django.db.models import QuerySet
from rest_framework.exceptions import NotFound

from apps.chat.models import Conversation, Message
from apps.chat.repositories import ConversationRepository, MessageRepository
from apps.projects.models import Project
from apps.projects.repositories import ProjectRepository
from apps.serving.models import Engine
from apps.serving.repositories import EngineRepository
from apps.versions.models import ModelVersion
from apps.versions.repositories import VersionRepository


class ConversationService:
    def __init__(self, user: User | AnonymousUser) -> None:
        self.user: User | AnonymousUser = user
        self.conversations: ConversationRepository = ConversationRepository()
        self.messages: MessageRepository = MessageRepository()
        self.projects: ProjectRepository = ProjectRepository()
        self.versions: VersionRepository = VersionRepository()
        self.engines: EngineRepository = EngineRepository()

    def project(self, project_id: str) -> Project:
        project: Project | None = self.projects.find(project_id)
        if project is None:
            raise NotFound
        return project

    def listing(self, project_id: str) -> QuerySet[Conversation]:
        return self.conversations.of_project(str(self.project(project_id).pk))

    def find(self, conversation_id: str) -> Conversation:
        conversation: Conversation | None = self.conversations.with_project(conversation_id)
        if conversation is None:
            raise NotFound
        return conversation

    def describe(self, conversation: Conversation) -> dict[str, Any]:
        version: ModelVersion | None = conversation.version
        return {
            "id": conversation.pk,
            "project": conversation.project_id,
            "title": conversation.title,
            "version": None if version is None else {"id": version.pk, "name": str(version)},
            "engine": None
            if conversation.engine is None
            else {"id": conversation.engine.pk, "name": conversation.engine.name},
            "system_prompt": conversation.system_prompt,
            "thinking": conversation.thinking,
            "generation": conversation.generation,
            "message_count": getattr(conversation, "message_count", None),
            "created_at": conversation.created_at,
            "updated_at": conversation.updated_at,
        }

    def create(self, *, project: str, **fields: Any) -> dict[str, Any]:
        owner: Project = self.project(project)
        version: ModelVersion | None = self._version(owner, fields.pop("version", None))
        conversation: Conversation = self.conversations.create(
            created_by=self._actor(),
            project=owner,
            version=version,
            thinking=fields.pop("thinking", owner.thinking),
            **fields,
        )
        return self.describe(conversation)

    def change(self, conversation_id: str, **fields: Any) -> dict[str, Any]:
        conversation: Conversation = self.find(conversation_id)
        if "version" in fields:
            fields["version"] = self._version(conversation.project, fields["version"])
        if "engine" in fields:
            fields["engine"] = self._engine(fields["engine"])
        if fields:
            conversation = self.conversations.update(conversation, **fields)
        return self.describe(conversation)

    def remove(self, conversation_id: str) -> None:
        self.conversations.soft_delete(self.find(conversation_id))

    def messages_of(self, conversation_id: str) -> QuerySet[Message]:
        return self.messages.of_conversation(str(self.find(conversation_id).pk))

    def _version(self, project: Project, version_id: object) -> ModelVersion | None:
        if version_id is None:
            return None
        version: ModelVersion | None = self.versions.find(str(version_id), project=project)
        if version is None:
            raise NotFound
        return version

    def _engine(self, engine_id: object) -> Engine | None:
        if engine_id is None:
            return None
        engine: Engine | None = self.engines.find(str(engine_id))
        if engine is None or not engine.enabled:
            raise NotFound
        return engine

    def _actor(self) -> User | None:
        return self.user if isinstance(self.user, User) else None


def describe_message(message: Message) -> dict[str, Any]:
    version: ModelVersion | None = message.version
    return {
        "id": message.pk,
        "position": message.position,
        "role": message.role,
        "status": message.status,
        "content": message.content,
        "thinking": message.thinking,
        "version": None if version is None else {"id": version.pk, "name": str(version)},
        "engine_name": message.engine_name,
        "finish_reason": message.finish_reason,
        "error_code": message.error_code,
        "tokens_prompt": message.tokens_prompt,
        "tokens_completion": message.tokens_completion,
        "latency_ms": message.latency_ms,
        "original_content": message.original_content if message.content_edited_at else None,
        "original_thinking": message.original_thinking if message.thinking_edited_at else None,
        "content_edited_at": message.content_edited_at,
        "thinking_edited_at": message.thinking_edited_at,
        "edited_by": _name(message.edited_by),
        "approved": message.approved,
        "approved_by": _name(message.approved_by),
        "include_in_training": message.include_in_training,
        "created_at": message.created_at,
        "updated_at": message.updated_at,
    }


def _name(user: User | None) -> str | None:
    return None if user is None else user.get_username()
