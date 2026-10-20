from __future__ import annotations

from django.contrib.auth.models import User
from django.db.models import QuerySet

from apps.common.repositories import BaseRepository
from apps.serving.models import ApiKey


class ApiKeyRepository(BaseRepository[ApiKey]):
    model = ApiKey

    def listing(self) -> QuerySet[ApiKey]:
        return self.active().select_related("created_by").order_by("-created_at")

    def owned_by(self, user: User) -> QuerySet[ApiKey]:
        return self.listing().filter(created_by=user)

    def by_digest(self, digest: str) -> ApiKey | None:
        return self.active().select_related("created_by").filter(digest=digest).first()
