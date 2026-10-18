from __future__ import annotations

from uuid import UUID

from django.db.models import QuerySet

from apps.common.repositories import BaseRepository
from apps.versions.models import Export, ModelVersion


class ExportRepository(BaseRepository[Export]):
    model = Export

    def of_version(self, version_id: str) -> QuerySet[Export]:
        return self.active().filter(version_id=UUID(version_id)).select_related("created_by")

    def ready_gguf(self, version: ModelVersion) -> Export | None:
        return (
            self.active()
            .filter(version=version, format=Export.Format.GGUF, status=Export.Status.READY)
            .order_by("-created_at")
            .first()
        )

    def with_version(self, export_id: str) -> Export | None:
        return (
            self.active()
            .select_related(
                "version", "version__project", "version__project__base_model", "created_by"
            )
            .filter(pk=export_id)
            .first()
        )
