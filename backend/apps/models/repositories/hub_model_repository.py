from __future__ import annotations

from django.db.models import QuerySet

from apps.common.repositories import BaseRepository
from apps.models.models import HubModel


class HubModelRepository(BaseRepository[HubModel]):
    model = HubModel

    def library(self) -> QuerySet[HubModel]:
        return self.active().order_by("-created_at")

    def find_by_repo(self, repo_id: str) -> HubModel | None:
        return self.active().filter(repo_id__iexact=repo_id).first()

    def by_repo(self, repo_ids: list[str]) -> dict[str, HubModel]:
        return {row.repo_id.lower(): row for row in self.active().filter(repo_id__in=repo_ids)}

    def in_use(self, model: HubModel) -> bool:
        return model.projects.filter(deleted_at__isnull=True).exists()

    def cancel_requested(self, model_id: str) -> bool:
        return self.active().filter(pk=model_id, cancel_requested=True).exists()

    def set_progress(self, model_id: str, downloaded_bytes: int) -> None:
        self.active().filter(pk=model_id).update(downloaded_bytes=downloaded_bytes)
