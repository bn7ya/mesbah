from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.common.repositories import BaseRepository
from apps.training.models import TrainingRun

FINISHED: tuple[str, ...] = (
    TrainingRun.Status.COMPLETED,
    TrainingRun.Status.FAILED,
    TrainingRun.Status.CANCELLED,
)


class RunRepository(BaseRepository[TrainingRun]):
    model = TrainingRun

    def active(self) -> QuerySet[TrainingRun]:
        return super().active().filter(project__deleted_at__isnull=True)

    def of_project(self, project_id: str) -> QuerySet[TrainingRun]:
        return (
            self.active()
            .filter(project_id=project_id)
            .select_related("parent", "version", "created_by")
            .order_by("-created_at")
        )

    def with_project(self, run_id: str) -> TrainingRun | None:
        return (
            self.active()
            .select_related("project", "project__base_model", "parent", "version", "created_by")
            .filter(pk=run_id)
            .first()
        )

    def unfinished(self) -> QuerySet[TrainingRun]:
        return self.active().exclude(status__in=FINISHED)

    def cancel_requested(self, run_id: str) -> bool:
        stopping: Q = Q(cancel_requested=True) | Q(project__deleted_at__isnull=False)
        return super().active().filter(stopping, pk=run_id).exists()
