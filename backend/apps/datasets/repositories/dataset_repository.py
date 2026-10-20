from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.common.repositories import BaseRepository
from apps.datasets.models import Dataset


class DatasetRepository(BaseRepository[Dataset]):
    model = Dataset

    def library(self) -> QuerySet[Dataset]:
        return self.active().select_related("created_by").order_by("-created_at")

    def imported_repos(self, repo_ids: list[str]) -> set[str]:
        found: QuerySet[Dataset] = self.active().filter(
            source=Dataset.Source.HUB, repo_id__in=repo_ids
        )
        return {repo.lower() for repo in found.values_list("repo_id", flat=True)}

    def should_stop(self, dataset_id: str) -> bool:
        stopping: Q = Q(cancel_requested=True) | Q(deleted_at__isnull=False)
        return self.all_including_deleted().filter(stopping, pk=dataset_id).exists()

    def set_progress(self, dataset_id: str, rows: int, skipped: int) -> None:
        self.active().filter(pk=dataset_id).update(rows=rows, skipped=skipped)
