"""`BaseRepository` — the only layer allowed to touch the ORM.

Repositories fetch and persist. They hold no business rules, make no
permission decisions, and raise no domain errors beyond `DoesNotExist`.
Everything that decides something belongs one layer up, in a service.
"""
from __future__ import annotations

from typing import Any, ClassVar
from uuid import UUID

from django.db import models
from django.utils import timezone


class BaseRepository[TModel: models.Model]:
    """Query surface for one model.

    Subclasses set `model` and add the queries their service needs::

        class ProjectRepository(BaseRepository[Project]):
            model = Project

            def get_for_owner(self, project_id: UUID, user) -> Project:
                return self.active().filter(created_by=user).get(pk=project_id)
    """

    model: ClassVar[type[models.Model]]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not getattr(cls, "model", None):
            raise TypeError(f"{cls.__name__} must set `model`.")

    # ----------------------------------------------------------- querysets

    def active(self) -> models.QuerySet[TModel]:
        """Rows that have not been soft-deleted. The default for reads."""
        return self.model.objects.all()

    def all_including_deleted(self) -> models.QuerySet[TModel]:
        """Every row, soft-deleted included. Reserved for audit/admin reads."""
        return self.model.all_objects.all()

    # -------------------------------------------------------------- single

    def get(self, pk: UUID | str, **filters: Any) -> TModel:
        """Fetch one active row. Raises `model.DoesNotExist` if there is none."""
        return self.active().get(pk=pk, **filters)

    def find(self, pk: UUID | str, **filters: Any) -> TModel | None:
        """Fetch one active row, or `None`."""
        return self.active().filter(pk=pk, **filters).first()

    def exists(self, **filters: Any) -> bool:
        return self.active().filter(**filters).exists()

    # -------------------------------------------------------------- writes

    def create(self, *, created_by=None, **fields: Any) -> TModel:
        return self.model.objects.create(created_by=created_by, **fields)

    def update(self, instance: TModel, **fields: Any) -> TModel:
        for name, value in fields.items():
            setattr(instance, name, value)
        instance.save(update_fields=[*fields.keys(), "updated_at"])
        return instance

    def soft_delete(self, instance: TModel) -> TModel:
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["deleted_at", "updated_at"])
        return instance

    def restore(self, instance: TModel) -> TModel:
        instance.deleted_at = None
        instance.save(update_fields=["deleted_at", "updated_at"])
        return instance

    def bulk_soft_delete(self, queryset: models.QuerySet[TModel]) -> int:
        """Soft-delete many rows in one statement."""
        return queryset.update(deleted_at=timezone.now())
