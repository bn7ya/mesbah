"""Soft-delete queryset and managers.

Every model in the Django side of Mesbah inherits `BaseModel` and is
soft-deleted: `delete()` sets `deleted_at` rather than removing the row.
Anything that needs to see removed rows asks for it by name, through
`all_objects`.
"""
from __future__ import annotations

from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    """A queryset whose `delete()` marks rows instead of removing them."""

    def delete(self):
        """Soft-delete every row in this queryset. Returns the number marked."""
        return self.update(deleted_at=timezone.now())

    def purge(self):
        """Really remove the rows. Reserved for data migrations."""
        return super().delete()

    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        return self.filter(deleted_at__isnull=False)


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """Default manager: soft-deleted rows are invisible."""

    def get_queryset(self) -> SoftDeleteQuerySet:
        return super().get_queryset().filter(deleted_at__isnull=True)


class AllObjectsManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """Escape hatch: every row, including the soft-deleted ones."""
