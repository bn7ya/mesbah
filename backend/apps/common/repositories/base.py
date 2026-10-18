from __future__ import annotations

from typing import Any
from uuid import UUID

from django.contrib.auth.base_user import AbstractBaseUser
from django.db import models
from django.utils import timezone

from apps.common.models import BaseModel


class BaseRepository[TModel: BaseModel]:
    model: type[TModel]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not getattr(cls, "model", None):
            raise TypeError(f"{cls.__name__} must set `model`.")

    def active(self) -> models.QuerySet[TModel]:
        return self.model.objects.all()

    def all_including_deleted(self) -> models.QuerySet[TModel]:
        return self.model.all_objects.all()

    def get(self, pk: UUID | str, **filters: Any) -> TModel:
        return self.active().get(pk=pk, **filters)

    def find(self, pk: UUID | str, **filters: Any) -> TModel | None:
        return self.active().filter(pk=pk, **filters).first()

    def exists(self, **filters: Any) -> bool:
        return self.active().filter(**filters).exists()

    def create(self, *, created_by: AbstractBaseUser | None = None, **fields: Any) -> TModel:
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
        return queryset.update(deleted_at=timezone.now())
