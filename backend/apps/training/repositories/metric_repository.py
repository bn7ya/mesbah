from __future__ import annotations

from uuid import UUID

from django.db.models import QuerySet

from apps.common.repositories import BaseRepository
from apps.training.models import TrainingMetric


class MetricRepository(BaseRepository[TrainingMetric]):
    model = TrainingMetric

    def of_run(self, run_id: str, after_step: int = 0) -> QuerySet[TrainingMetric]:
        return self.active().filter(run_id=UUID(run_id), step__gt=after_step).order_by("step")

    def record(self, rows: list[TrainingMetric]) -> None:
        self.model.objects.bulk_create(rows, ignore_conflicts=True)
