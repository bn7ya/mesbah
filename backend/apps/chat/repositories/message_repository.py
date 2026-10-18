from __future__ import annotations

from django.db.models import Max, QuerySet

from apps.chat.models import Conversation, Message
from apps.common.repositories import BaseRepository


class MessageRepository(BaseRepository[Message]):
    model = Message

    def of_conversation(self, conversation_id: str) -> QuerySet[Message]:
        return (
            self.active()
            .filter(conversation_id=conversation_id)
            .select_related("version", "edited_by", "approved_by")
            .order_by("position")
        )

    def locked(self, message_id: str) -> Message | None:
        return (
            self.active()
            .select_for_update(of=("self",))
            .select_related("version", "edited_by", "approved_by")
            .filter(pk=message_id)
            .first()
        )

    def history(self, conversation: Conversation) -> QuerySet[Message]:
        return (
            self.active()
            .filter(conversation=conversation)
            .exclude(status__in=[Message.Status.FAILED, Message.Status.STREAMING])
            .order_by("position")
        )

    def approved_replies(self, project_id: str) -> QuerySet[Message]:
        return (
            self.active()
            .filter(
                conversation__project_id=project_id,
                conversation__deleted_at__isnull=True,
                role=Message.Role.ASSISTANT,
                approved=True,
                include_in_training=True,
            )
            .exclude(status=Message.Status.STREAMING)
            .select_related("conversation", "conversation__project", "approved_by")
            .order_by("created_at")
        )

    def before(self, message: Message) -> QuerySet[Message]:
        return (
            self.active()
            .filter(conversation_id=message.conversation_id, position__lt=message.position)
            .exclude(status__in=[Message.Status.FAILED, Message.Status.STREAMING])
            .order_by("position")
        )

    def next_position(self, conversation: Conversation) -> int:
        highest: int | None = (
            self.all_including_deleted()
            .filter(conversation=conversation)
            .aggregate(highest=Max("position"))["highest"]
        )
        return 0 if highest is None else highest + 1
