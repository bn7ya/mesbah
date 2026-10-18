from __future__ import annotations

from django.db.models import Count, Q, QuerySet

from apps.chat.models import Conversation
from apps.common.repositories import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    model = Conversation

    def of_project(self, project_id: str) -> QuerySet[Conversation]:
        rows: QuerySet[Conversation] = (
            self.active()
            .filter(project_id=project_id)
            .select_related("version", "engine")
            .annotate(message_count=Count("messages", filter=Q(messages__deleted_at__isnull=True)))
            .order_by("-updated_at")
        )
        return rows

    def locked(self, conversation_id: str) -> Conversation | None:
        return (
            self.active()
            .select_for_update(of=("self",))
            .select_related("project", "project__active_version", "version", "engine")
            .filter(pk=conversation_id)
            .first()
        )

    def with_project(self, conversation_id: str) -> Conversation | None:
        return (
            self.active()
            .select_related(
                "project", "project__base_model", "project__active_version", "version", "engine"
            )
            .filter(pk=conversation_id)
            .first()
        )
