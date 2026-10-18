from __future__ import annotations

import shutil
from fnmatch import fnmatch
from typing import Any

from django.contrib.auth.models import AnonymousUser, User
from django.core.cache import cache
from django.db import transaction
from django.db.models import QuerySet
from rest_framework.exceptions import NotFound

from apps.models.models import HubModel
from apps.models.repositories import HubModelRepository
from apps.models.services.errors import (
    AlreadyInLibrary,
    ModelInUse,
    NotDownloadable,
    NotEnoughDisk,
)
from apps.models.services.hub_client import HubClient, HubDetail, HubResult
from apps.models.services.storage import hub_cache_dir
from apps.system.services import SystemService
from mesbah import sizing
from mesbah.download import ignore_patterns, repo_cache_dir

FEATURED_KEY: str = "models:featured"
FEATURED_SECONDS: int = 15 * 60
SEARCH_LIMIT: int = 24
DEFAULT_TASK: str = "text-generation"
WEIGHT_SUFFIXES: tuple[str, ...] = (".safetensors", ".bin")
DISK_MARGIN: float = 1.05


def _fits(parameters: int | None, vram: int) -> dict[str, dict[str, Any]]:
    shown: dict[str, int | None] = {
        "chat": sizing.chat_bytes(parameters, four_bit=True) if parameters else None,
        "chat_full": sizing.chat_bytes(parameters, four_bit=False) if parameters else None,
        "training": sizing.qlora_bytes(parameters) if parameters else None,
    }
    return {use: vars(sizing.fit(required, vram)) for use, required in shown.items()}


class ModelService:
    def __init__(self, user: User | AnonymousUser) -> None:
        self.user: User | AnonymousUser = user
        self.models: HubModelRepository = HubModelRepository()
        self.system: SystemService = SystemService(user)

    def hub(self) -> HubClient:
        return HubClient(self.system.huggingface_token(), hub_cache_dir())

    def library(self) -> QuerySet[HubModel]:
        return self.models.library()

    def find(self, model_id: str) -> HubModel:
        row: HubModel | None = self.models.find(model_id)
        if row is None:
            raise NotFound
        return row

    def describe(self, row: HubModel, vram: int | None = None) -> dict[str, Any]:
        available: int = self.system.usable_vram_bytes() if vram is None else vram
        return {
            "id": row.pk,
            "repo_id": row.repo_id,
            "revision": row.revision,
            "family": row.family,
            "model_type": row.model_type,
            "architecture": row.architecture,
            "parameters": row.parameters,
            "active_parameters": row.active_parameters,
            "license": row.license,
            "gated": row.gated,
            "supports_thinking": row.supports_thinking,
            "has_chat_template": row.has_chat_template,
            "size_bytes": row.size_bytes,
            "downloaded_bytes": row.downloaded_bytes,
            "status": row.status,
            "error_code": row.error_code,
            "downloaded_at": row.downloaded_at,
            "created_at": row.created_at,
            "fit": _fits(row.parameters, available),
        }

    def search(self, query: str, task: str) -> list[dict[str, Any]]:
        results: list[HubResult] = self.hub().search(query.strip(), task, SEARCH_LIMIT)
        return self._listed(results)

    def featured(self) -> list[dict[str, Any]]:
        cached: object = cache.get(FEATURED_KEY)
        if isinstance(cached, list):
            return self._listed(cached)
        results: list[HubResult] = self.hub().search("", DEFAULT_TASK, SEARCH_LIMIT)
        cache.set(FEATURED_KEY, results, FEATURED_SECONDS)
        return self._listed(results)

    def inspect(self, repo_id: str) -> dict[str, Any]:
        detail: HubDetail = self.hub().detail(repo_id)
        shape: sizing.Architecture = sizing.architecture(detail.config)
        active: int | None = sizing.active_parameters(detail.result.parameters, shape)
        existing: HubModel | None = self.models.find_by_repo(repo_id)
        vram: int = self.system.usable_vram_bytes()
        return {
            **vars(detail.result),
            "revision": detail.revision,
            "family": shape.family,
            "architecture": vars(shape),
            "active_parameters": active,
            "has_chat_template": detail.has_chat_template,
            "downloadable": self._downloadable(detail),
            "size_bytes": self._size(detail),
            "fit": _fits(detail.result.parameters, vram),
            "in_library": None
            if existing is None
            else {"id": existing.pk, "status": existing.status},
        }

    @transaction.atomic
    def add(self, repo_id: str) -> dict[str, Any]:
        existing: HubModel | None = self.models.find_by_repo(repo_id)
        if existing is not None and existing.status not in {
            HubModel.Status.FAILED,
            HubModel.Status.CANCELLED,
        }:
            raise AlreadyInLibrary
        detail: HubDetail = self.hub().detail(repo_id)
        if not self._downloadable(detail):
            raise NotDownloadable
        size: int = self._size(detail)
        if shutil.disk_usage(hub_cache_dir()).free < size * DISK_MARGIN:
            raise NotEnoughDisk
        shape: sizing.Architecture = sizing.architecture(detail.config)
        fields: dict[str, Any] = {
            "revision": detail.revision,
            "pipeline_tag": detail.result.pipeline_tag,
            "family": shape.family,
            "model_type": shape.model_type or detail.result.model_type,
            "architecture": vars(shape),
            "parameters": detail.result.parameters,
            "active_parameters": sizing.active_parameters(detail.result.parameters, shape),
            "license": detail.result.license,
            "gated": detail.result.gated,
            "supports_thinking": detail.result.supports_thinking,
            "has_chat_template": detail.has_chat_template,
            "files": [name for name, _ in detail.files],
            "size_bytes": size,
            "downloaded_bytes": 0,
            "status": HubModel.Status.QUEUED,
            "error_code": "",
            "cancel_requested": False,
        }
        row: HubModel
        if existing is None:
            row = self.models.create(
                created_by=self._actor(), repo_id=detail.result.repo_id, **fields
            )
        else:
            row = self.models.update(existing, **fields)
        self._enqueue(row)
        return self.describe(row)

    def cancel(self, model_id: str) -> dict[str, Any]:
        row: HubModel = self.find(model_id)
        if row.status in {HubModel.Status.QUEUED, HubModel.Status.DOWNLOADING}:
            row = self.models.update(row, cancel_requested=True)
        return self.describe(row)

    def retry(self, model_id: str) -> dict[str, Any]:
        row: HubModel = self.find(model_id)
        return self.add(row.repo_id)

    def remove(self, model_id: str) -> None:
        row: HubModel = self.find(model_id)
        if self.models.in_use(row):
            raise ModelInUse
        self.models.update(row, cancel_requested=True)
        self.models.soft_delete(row)
        shutil.rmtree(repo_cache_dir(hub_cache_dir(), row.repo_id), ignore_errors=True)

    def _listed(self, results: list[HubResult]) -> list[dict[str, Any]]:
        known: dict[str, HubModel] = self.models.by_repo([result.repo_id for result in results])
        vram: int = self.system.usable_vram_bytes()
        listed: list[dict[str, Any]] = []
        for result in results:
            row: HubModel | None = known.get(result.repo_id.lower())
            listed.append(
                {
                    **vars(result),
                    "fit": _fits(result.parameters, vram),
                    "in_library": None if row is None else {"id": row.pk, "status": row.status},
                }
            )
        return listed

    @staticmethod
    def _downloadable(detail: HubDetail) -> bool:
        return any(name.endswith(WEIGHT_SUFFIXES) for name, _ in detail.files)

    @staticmethod
    def _size(detail: HubDetail) -> int:
        skipped: list[str] = ignore_patterns([name for name, _ in detail.files])
        return sum(
            size
            for name, size in detail.files
            if not any(fnmatch(name, pattern) for pattern in skipped)
        )

    def _actor(self) -> User | None:
        return self.user if isinstance(self.user, User) else None

    @staticmethod
    def _enqueue(row: HubModel) -> None:
        from apps.models.tasks import download_model

        model_id: str = str(row.pk)
        transaction.on_commit(lambda: download_model.delay(model_id))
