from __future__ import annotations

import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from django.contrib.auth.models import AnonymousUser, User

from apps.models.models import HubModel
from apps.projects.models import Project
from apps.projects.repositories import ProjectRepository
from apps.serving.services.deployment_service import DeploymentService, Target
from apps.serving.services.engine_client import EngineClient, Piece
from apps.versions.models import ModelVersion
from apps.versions.repositories import VersionRepository

LATEST: str = "latest"
TAG: re.Pattern[str] = re.compile(r"^v(\d+)$")


class UnknownModel(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name: str = name


@dataclass(frozen=True)
class Served:
    name: str
    project: Project
    version: ModelVersion
    active: bool


@dataclass
class Collected:
    content: list[str] = field(default_factory=list)
    thinking: list[str] = field(default_factory=list)
    finish_reason: str = "stop"
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class GatewayService:
    def __init__(self, user: User | AnonymousUser) -> None:
        self.user: User | AnonymousUser = user
        self.projects: ProjectRepository = ProjectRepository()
        self.versions: VersionRepository = VersionRepository()
        self.deployments: DeploymentService = DeploymentService(user)

    def served(self) -> list[Served]:
        found: list[Served] = []
        for project in self.projects.listing():
            for version in self.versions.of_project(str(project.pk)):
                active: bool = version.pk == project.active_version_id
                if active:
                    found.append(Served(project.slug, project, version, active))
                found.append(Served(f"{project.slug}:v{version.number}", project, version, active))
        return found

    def resolve(self, name: str) -> Served:
        slug, _, tag = name.partition(":")
        project: Project | None = self.projects.find_by_slug(slug)
        if project is None:
            raise UnknownModel(name)
        if tag in ("", LATEST):
            if project.active_version is None:
                raise UnknownModel(name)
            return Served(name, project, project.active_version, True)
        number: re.Match[str] | None = TAG.match(tag)
        version: ModelVersion | None = (
            None
            if number is None
            else self.versions.of_project(str(project.pk)).filter(number=int(number[1])).first()
        )
        if version is None:
            raise UnknownModel(name)
        return Served(name, project, version, version.pk == project.active_version_id)

    def target(self, served: Served) -> Target:
        return self.deployments.target(served.version)

    @staticmethod
    def thinking_default(served: Served) -> bool:
        base: HubModel | None = served.project.base_model
        return served.project.thinking and base is not None and base.supports_thinking

    @staticmethod
    async def stream(target: Target, body: dict[str, object]) -> AsyncIterator[Piece]:
        async for piece in EngineClient(target.endpoint).stream_chat(
            {**body, "model": target.model}
        ):
            yield piece

    @staticmethod
    async def collect(target: Target, body: dict[str, object]) -> Collected:
        reply: Collected = Collected()
        async for piece in GatewayService.stream(target, body):
            if piece.kind == "content":
                reply.content.append(piece.text)
            elif piece.kind == "thinking":
                reply.thinking.append(piece.text)
            elif piece.kind == "finish":
                reply.finish_reason = piece.text
            else:
                reply.prompt_tokens = piece.prompt_tokens
                reply.completion_tokens = piece.completion_tokens
        return reply
