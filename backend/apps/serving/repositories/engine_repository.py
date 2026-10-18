from __future__ import annotations

from django.db.models import QuerySet

from apps.common.repositories import BaseRepository
from apps.serving.models import Engine


class EngineRepository(BaseRepository[Engine]):
    model = Engine

    def listing(self) -> QuerySet[Engine]:
        return self.active().order_by("-is_default", "created_at")

    def default(self) -> Engine | None:
        return self.active().filter(is_default=True, enabled=True).first()

    def clear_default(self) -> int:
        return self.active().filter(is_default=True).update(is_default=False)

    def builtin(self) -> Engine | None:
        return self.active().filter(kind=Engine.Kind.BUILTIN).first()
