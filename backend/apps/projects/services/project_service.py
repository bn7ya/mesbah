from __future__ import annotations

from typing import Any

from django.contrib.auth.models import AnonymousUser, User
from django.db import transaction
from django.db.models import QuerySet
from django.utils.text import slugify
from rest_framework.exceptions import NotFound

from apps.models.models import HubModel
from apps.models.repositories import HubModelRepository
from apps.projects.models import Project
from apps.projects.repositories import ProjectRepository
from apps.projects.services.errors import BaseModelNotReady
from apps.versions.models import ModelVersion
from apps.versions.services import VersionService

SLUG_LENGTH: int = 60


class ProjectService:
    def __init__(self, user: User | AnonymousUser) -> None:
        self.user: User | AnonymousUser = user
        self.projects: ProjectRepository = ProjectRepository()
        self.models: HubModelRepository = HubModelRepository()

    def listing(self) -> QuerySet[Project]:
        return self.projects.listing()

    def find(self, project_id: str) -> Project:
        project: Project | None = self.projects.find(project_id)
        if project is None:
            raise NotFound
        return project

    def describe(self, project: Project) -> dict[str, Any]:
        base: HubModel | None = project.base_model
        active: ModelVersion | None = project.active_version
        return {
            "id": project.pk,
            "name": project.name,
            "slug": project.slug,
            "description": project.description,
            "kind": project.kind,
            "base_model": None
            if base is None
            else {
                "id": base.pk,
                "repo_id": base.repo_id,
                "family": base.family,
                "parameters": base.parameters,
                "supports_thinking": base.supports_thinking,
                "status": base.status,
            },
            "active_version": None
            if active is None
            else {"id": active.pk, "number": active.number, "name": str(active)},
            "system_prompt": project.system_prompt,
            "thinking": project.thinking,
            "generation": project.generation,
            "created_at": project.created_at,
            "updated_at": project.updated_at,
        }

    @transaction.atomic
    def create(self, *, name: str, base_model: str, **fields: Any) -> dict[str, Any]:
        model: HubModel | None = self.models.find(base_model)
        if model is None or model.status != HubModel.Status.READY:
            raise BaseModelNotReady
        project: Project = self.projects.create(
            created_by=self._actor(),
            name=name,
            slug=self._unique_slug(name),
            kind=Project.Kind.FINETUNE,
            base_model=model,
            thinking=fields.pop("thinking", model.supports_thinking),
            **fields,
        )
        VersionService(self.user).create_root(project)
        return self.describe(project)

    def change(self, project_id: str, **fields: Any) -> dict[str, Any]:
        project: Project = self.find(project_id)
        if "name" in fields and fields["name"] != project.name:
            fields["slug"] = self._unique_slug(fields["name"], besides=str(project.pk))
        if fields:
            project = self.projects.update(project, **fields)
        return self.describe(project)

    def remove(self, project_id: str) -> None:
        self.projects.soft_delete(self.find(project_id))

    def _unique_slug(self, name: str, besides: str | None = None) -> str:
        base: str = slugify(name)[:SLUG_LENGTH].strip("-") or "project"
        slug: str = base
        suffix: int = 2
        while self.projects.slug_taken(slug, besides=besides):
            slug = f"{base}-{suffix}"
            suffix += 1
        return slug

    def _actor(self) -> User | None:
        return self.user if isinstance(self.user, User) else None
