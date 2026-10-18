from __future__ import annotations

from typing import Any

from django.contrib.auth.models import AnonymousUser, User
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.models.models import HubModel
from apps.models.repositories import HubModelRepository
from apps.serving.models import Engine
from apps.serving.repositories import DeploymentRepository, EngineRepository
from apps.serving.services.deployment_service import DeploymentService, endpoint_of
from apps.serving.services.engine_client import EngineClient, EngineError, Json
from apps.serving.services.errors import BuiltinEngineKept
from apps.system.services import SecretBox
from apps.versions.models import ModelVersion
from apps.versions.repositories import VersionRepository

BUILTIN_FIELDS: frozenset[str] = frozenset({"name", "enabled", "is_default"})
IDLE: dict[str, Any] = {
    "running": True,
    "loaded": False,
    "busy": False,
    "device": None,
    "quantized": False,
    "base_model": None,
    "versions": [],
}


class EngineService:
    def __init__(self, user: User | AnonymousUser) -> None:
        self.user: User | AnonymousUser = user
        self.engines: EngineRepository = EngineRepository()
        self.deployments: DeploymentRepository = DeploymentRepository()
        self.models: HubModelRepository = HubModelRepository()
        self.versions: VersionRepository = VersionRepository()

    def listing(self) -> QuerySet[Engine]:
        return self.engines.listing()

    def find(self, engine_id: str) -> Engine:
        engine: Engine | None = self.engines.find(engine_id)
        if engine is None:
            raise NotFound
        return engine

    def describe(self, engine: Engine) -> dict[str, Any]:
        return {
            "id": engine.pk,
            "name": engine.name,
            "kind": engine.kind,
            "base_url": endpoint_of(engine).base_url,
            "model_name": engine.model_name,
            "has_api_key": bool(engine.sealed_api_key),
            "managed": engine.kind == Engine.Kind.BUILTIN,
            "enabled": engine.enabled,
            "is_default": engine.is_default,
            "last_seen_at": engine.last_seen_at,
            "state": self._state(engine),
        }

    @transaction.atomic
    def create(self, *, api_key: str = "", is_default: bool = False, **fields: Any) -> Engine:
        fields["base_url"] = str(fields["base_url"]).strip().rstrip("/")
        if is_default:
            self.engines.clear_default()
        return self.engines.create(
            created_by=self.user if isinstance(self.user, User) else None,
            sealed_api_key=SecretBox().seal(api_key) if api_key else "",
            is_default=is_default,
            **fields,
        )

    @transaction.atomic
    def change(self, engine_id: str, **fields: Any) -> Engine:
        engine: Engine = self.find(engine_id)
        if engine.kind == Engine.Kind.BUILTIN:
            fields = {name: value for name, value in fields.items() if name in BUILTIN_FIELDS}
        if "base_url" in fields:
            fields["base_url"] = str(fields["base_url"]).strip().rstrip("/")
        if "api_key" in fields:
            key: str = fields.pop("api_key")
            fields["sealed_api_key"] = SecretBox().seal(key) if key else ""
        if fields.get("is_default"):
            self.engines.clear_default()
        return self.engines.update(engine, **fields) if fields else engine

    def remove(self, engine_id: str) -> None:
        engine: Engine = self.find(engine_id)
        if engine.kind == Engine.Kind.BUILTIN:
            raise BuiltinEngineKept
        self.engines.soft_delete(engine)

    def unload(self, engine_id: str) -> dict[str, Any]:
        engine: Engine = self.find(engine_id)
        if engine.kind == Engine.Kind.BUILTIN:
            DeploymentService(self.user).release()
        return self.describe(engine)

    def _state(self, engine: Engine) -> dict[str, Any]:
        if engine.kind != Engine.Kind.BUILTIN:
            return self._external_state(engine)
        client: EngineClient = EngineClient(endpoint_of(engine))
        try:
            status: Json = client.status()
        except EngineError:
            return {**IDLE, "running": False}
        self.engines.update(engine, last_seen_at=timezone.now())
        if not status.get("loaded"):
            return {**IDLE, "busy": bool(status.get("busy"))}
        base_path: object = status.get("base")
        base: HubModel | None = (
            self.models.find_by_local_path(base_path) if isinstance(base_path, str) else None
        )
        return {
            "running": True,
            "loaded": True,
            "busy": bool(status.get("busy")),
            "device": status.get("device"),
            "quantized": bool(status.get("quantized")),
            "base_model": None if base is None else {"id": base.pk, "repo_id": base.repo_id},
            "versions": self._versions(status.get("adapters")),
        }

    def _external_state(self, engine: Engine) -> dict[str, Any]:
        client: EngineClient = EngineClient(endpoint_of(engine))
        try:
            listed: object = (
                client.get("/api/tags").get("models")
                if engine.kind == Engine.Kind.OLLAMA
                else client.models()
            )
        except EngineError:
            return {**IDLE, "running": False}
        self.engines.update(engine, last_seen_at=timezone.now())
        loaded: list[str] = [
            str(deployment.version.pk) for deployment in self.deployments.on_engine(engine)
        ]
        return {
            **IDLE,
            "loaded": bool(listed),
            "versions": self._versions([{"name": name} for name in loaded]),
        }

    def _versions(self, adapters: object) -> list[dict[str, Any]]:
        names: list[str] = [
            adapter["name"]
            for adapter in (adapters if isinstance(adapters, list) else [])
            if isinstance(adapter, dict) and isinstance(adapter.get("name"), str)
        ]
        loaded: list[ModelVersion] = list(self.versions.with_ids(names))
        return [
            {
                "id": version.pk,
                "name": str(version),
                "number": version.number,
                "project": {"id": version.project_id, "name": version.project.name},
            }
            for version in loaded
        ]
