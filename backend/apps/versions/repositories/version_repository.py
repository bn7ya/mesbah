from __future__ import annotations

from django.db.models import Count, Max, Q, QuerySet

from apps.common.repositories import BaseRepository
from apps.versions.models import ModelVersion


class VersionRepository(BaseRepository[ModelVersion]):
    model = ModelVersion

    def of_project(self, project_id: str) -> QuerySet[ModelVersion]:
        rows: QuerySet[ModelVersion] = (
            self.active()
            .filter(project_id=project_id)
            .select_related("created_by")
            .annotate(children_count=Count("children", filter=Q(children__deleted_at__isnull=True)))
            .order_by("number")
        )
        return rows

    def root_of(self, project_id: str) -> ModelVersion | None:
        return self.active().filter(project_id=project_id, parent__isnull=True, number=0).first()

    def next_number(self, project_id: str) -> int:
        highest: int | None = (
            self.all_including_deleted()
            .filter(project_id=project_id)
            .aggregate(highest=Max("number"))["highest"]
        )
        return 0 if highest is None else highest + 1

    def children_of(self, version: ModelVersion) -> QuerySet[ModelVersion]:
        return self.active().filter(parent=version)

    def reparent(self, children: QuerySet[ModelVersion], parent: ModelVersion | None) -> int:
        return children.update(parent=parent)
