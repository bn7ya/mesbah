from __future__ import annotations

from typing import Self

from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet[TModel: models.Model](models.QuerySet[TModel, TModel]):
    def delete(self) -> tuple[int, dict[str, int]]:
        marked: int = self.update(deleted_at=timezone.now())
        return marked, {self.model._meta.label: marked}

    def purge(self) -> tuple[int, dict[str, int]]:
        return super().delete()

    def alive(self) -> Self:
        return self.filter(deleted_at__isnull=True)

    def dead(self) -> Self:
        return self.filter(deleted_at__isnull=False)


class SoftDeleteManager[TModel: models.Model](models.Manager[TModel]):
    def get_queryset(self) -> SoftDeleteQuerySet[TModel]:
        return SoftDeleteQuerySet(self.model, using=self._db).alive()


class AllObjectsManager[TModel: models.Model](models.Manager[TModel]):
    def get_queryset(self) -> SoftDeleteQuerySet[TModel]:
        return SoftDeleteQuerySet(self.model, using=self._db)
