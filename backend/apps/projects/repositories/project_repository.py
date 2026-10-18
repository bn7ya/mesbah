from __future__ import annotations

from django.db.models import QuerySet

from apps.common.repositories import BaseRepository
from apps.projects.models import Project


class ProjectRepository(BaseRepository[Project]):
    model = Project

    def listing(self) -> QuerySet[Project]:
        return self.active().select_related("base_model", "active_version").order_by("-updated_at")

    def slug_taken(self, slug: str, *, besides: str | None = None) -> bool:
        taken: QuerySet[Project] = self.active().filter(slug=slug)
        if besides is not None:
            taken = taken.exclude(pk=besides)
        return taken.exists()

    def find_by_slug(self, slug: str) -> Project | None:
        return self.active().select_related("base_model").filter(slug=slug).first()
