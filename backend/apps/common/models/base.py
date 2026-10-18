from __future__ import annotations

from uuid import uuid4

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.managers import AllObjectsManager, SoftDeleteManager


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def delete(
        self, using: str | None = None, keep_parents: bool = False
    ) -> tuple[int, dict[str, int]]:
        self.deleted_at = timezone.now()
        self.save(using=using, update_fields=["deleted_at", "updated_at"])
        return (1, {self._meta.label: 1})

    def restore(self, using: str | None = None) -> None:
        self.deleted_at = None
        self.save(using=using, update_fields=["deleted_at", "updated_at"])

    def purge(
        self, using: str | None = None, keep_parents: bool = False
    ) -> tuple[int, dict[str, int]]:
        return super().delete(using=using, keep_parents=keep_parents)
