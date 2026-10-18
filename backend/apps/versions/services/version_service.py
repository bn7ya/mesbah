from __future__ import annotations

from typing import Any

from django.contrib.auth.models import AnonymousUser, User
from django.db import transaction
from django.db.models import QuerySet
from rest_framework.exceptions import NotFound

from apps.projects.models import Project
from apps.projects.repositories import ProjectRepository
from apps.versions.models import ModelVersion
from apps.versions.repositories import VersionRepository
from apps.versions.services.errors import ActiveVersionKept, RootVersionKept

ROOT_NUMBER: int = 0


class VersionService:
    def __init__(self, user: User | AnonymousUser) -> None:
        self.user: User | AnonymousUser = user
        self.versions: VersionRepository = VersionRepository()
        self.projects: ProjectRepository = ProjectRepository()

    def project(self, project_id: str) -> Project:
        project: Project | None = self.projects.find(project_id)
        if project is None:
            raise NotFound
        return project

    def tree(self, project_id: str) -> QuerySet[ModelVersion]:
        return self.versions.of_project(str(self.project(project_id).pk))

    def find(self, version_id: str) -> ModelVersion:
        version: ModelVersion | None = self.versions.find(version_id)
        if version is None:
            raise NotFound
        return version

    def describe(self, version: ModelVersion, active_id: object = None) -> dict[str, Any]:
        active: object = active_id if active_id is not None else version.project.active_version_id
        stats: dict[str, Any] = version.delta_stats or {}
        return {
            "id": version.pk,
            "number": version.number,
            "name": str(version),
            "notes": version.notes,
            "kind": version.kind,
            "parent_id": version.parent_id,
            "is_active": version.pk == active,
            "children_count": getattr(version, "children_count", None),
            "size_bytes": version.size_bytes,
            "full_size_bytes": version.full_size_bytes,
            "lora_rank": version.lora_rank,
            "trains_biases": version.trains_biases,
            "delta": None
            if not stats
            else {
                "total_norm": stats.get("total_norm"),
                "change_from_parent": stats.get("change_from_parent"),
                "parameters": stats.get("parameters"),
            },
            "metrics": version.metrics,
            "created_at": version.created_at,
            "created_by": version.created_by.get_username() if version.created_by else None,
        }

    def changes(self, version_id: str) -> dict[str, Any]:
        version: ModelVersion = self.find(version_id)
        stats: dict[str, Any] = version.delta_stats or {}
        grid: dict[int, dict[str, float]] = {}
        modules: set[str] = set()
        for entry in stats.get("layers", []):
            layer: object = entry.get("layer")
            module: object = entry.get("module")
            norm: object = entry.get("norm")
            if isinstance(layer, int) and isinstance(module, str) and isinstance(norm, int | float):
                grid.setdefault(layer, {})[module] = float(norm)
                modules.add(module)
        return {
            "version": version.pk,
            "modules": sorted(modules),
            "layers": [{"layer": layer, "norms": grid[layer]} for layer in sorted(grid)],
            "total_norm": stats.get("total_norm"),
            "change_from_parent": stats.get("change_from_parent"),
            "parameters": stats.get("parameters"),
            "rank": stats.get("rank"),
        }

    def create_root(self, project: Project) -> ModelVersion:
        root: ModelVersion = self.versions.create(
            created_by=self._actor(),
            project=project,
            number=ROOT_NUMBER,
            kind=ModelVersion.Kind.BASE,
            name="base",
            full_size_bytes=0 if project.base_model is None else project.base_model.size_bytes,
        )
        self.projects.update(project, active_version=root)
        return root

    def record_trained(
        self, project: Project, parent: ModelVersion | None, **fields: Any
    ) -> ModelVersion:
        return self.versions.create(
            created_by=self._actor(),
            project=project,
            parent=parent,
            number=self.versions.next_number(str(project.pk)),
            kind=ModelVersion.Kind.LORA,
            **fields,
        )

    @transaction.atomic
    def activate(self, version_id: str) -> dict[str, Any]:
        version: ModelVersion = self.find(version_id)
        self.projects.update(version.project, active_version=version)
        return self.describe(version, version.pk)

    def change(self, version_id: str, **fields: str) -> dict[str, Any]:
        version: ModelVersion = self.find(version_id)
        if fields:
            version = self.versions.update(version, **fields)
        return self.describe(version)

    @transaction.atomic
    def remove(self, version_id: str) -> None:
        version: ModelVersion = self.find(version_id)
        if version.parent_id is None:
            raise RootVersionKept
        if version.project.active_version_id == version.pk:
            raise ActiveVersionKept
        self.versions.reparent(self.versions.children_of(version), version.parent)
        self.versions.soft_delete(version)

    def _actor(self) -> User | None:
        return self.user if isinstance(self.user, User) else None
