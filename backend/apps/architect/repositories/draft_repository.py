from __future__ import annotations

from django.db.models import QuerySet

from apps.architect.models import ArchitectureDraft
from apps.common.repositories import BaseRepository


class DraftRepository(BaseRepository[ArchitectureDraft]):
    model = ArchitectureDraft

    def listing(self) -> QuerySet[ArchitectureDraft]:
        return self.active().select_related("created_by").order_by("-updated_at")
