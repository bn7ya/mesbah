from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from django.utils import timezone

from apps.models.models import HubModel
from apps.serving.models import Deployment, Engine
from apps.serving.repositories import DeploymentRepository, EngineRepository
from apps.serving.services.engine_client import Endpoint, EngineClient, EngineError, Json
from apps.serving.services.errors import EngineFailed, ModelNotOnDisk, NoEngine
from apps.system.services import SecretBox, SystemService
from apps.training.models import TrainingRun
from apps.training.repositories import RunRepository
from apps.versions.models import Export, ModelVersion
from apps.versions.repositories import ExportRepository
from mesbah import sizing

BASE_NAME: str = "base"
CHUNK: int = 1024 * 1024


@dataclass(frozen=True)
class Target:
    endpoint: Endpoint
    model: str
    engine_name: str


def served_name(version: ModelVersion) -> str:
    return str(version.pk) if version.kind == ModelVersion.Kind.LORA else BASE_NAME


def builtin_endpoint() -> Endpoint:
    return Endpoint(settings.MESBAH_RUNTIME_URL, settings.MESBAH_RUNTIME_TOKEN or None)


def endpoint_of(engine: Engine) -> Endpoint:
    if engine.kind == Engine.Kind.BUILTIN:
        return builtin_endpoint()
    key: str | None = SecretBox().open(engine.sealed_api_key) if engine.sealed_api_key else None
    return Endpoint(engine.base_url.rstrip("/"), key)


def external_name(version: ModelVersion) -> str:
    return f"{version.project.slug}-v{version.number}"


class DeploymentService:
    def __init__(self, user: User | AnonymousUser) -> None:
        self.user: User | AnonymousUser = user
        self.engines: EngineRepository = EngineRepository()
        self.deployments: DeploymentRepository = DeploymentRepository()
        self.exports: ExportRepository = ExportRepository()
        self.runs: RunRepository = RunRepository()
        self.system: SystemService = SystemService(user)

    def target(self, version: ModelVersion, engine: Engine | None = None) -> Target:
        chosen: Engine | None = engine or self.engines.default()
        if chosen is None or not chosen.enabled:
            raise NoEngine
        base: HubModel | None = version.project.base_model
        if base is None or base.status != HubModel.Status.READY or not base.local_path:
            raise ModelNotOnDisk
        client: EngineClient = EngineClient(endpoint_of(chosen))
        try:
            model: str
            if chosen.kind == Engine.Kind.BUILTIN:
                model = self._on_builtin(chosen, client, base, version)
            elif chosen.kind == Engine.Kind.VLLM:
                model = self._on_vllm(chosen, client, base, version)
            elif chosen.kind == Engine.Kind.OLLAMA:
                model = self._on_ollama(chosen, client, version)
            else:
                model = chosen.model_name or "default"
        except EngineError as error:
            raise EngineFailed(error.code, error.detail) from error
        self.engines.update(chosen, last_seen_at=timezone.now())
        return Target(endpoint_of(chosen), model, chosen.name)

    def release(self) -> None:
        engine: Engine | None = self.engines.builtin()
        if engine is None:
            return
        try:
            EngineClient(endpoint_of(engine)).unload()
        except EngineError as error:
            if error.code != "engine_unreachable":
                raise EngineFailed(error.code, error.detail) from error
        self.deployments.mark_unloaded(engine)

    def _on_builtin(
        self, engine: Engine, client: EngineClient, base: HubModel, version: ModelVersion
    ) -> str:
        name: str = served_name(version)
        if _serves(client.status(), base.local_path, name, version.storage_dir):
            return name
        if self.runs.unfinished().exclude(status=TrainingRun.Status.QUEUED).exists():
            raise EngineError("training_in_progress", "A training run is using the memory.")
        deployment: Deployment = self._loading(engine, version, name)
        try:
            client.load(self._spec(base, version, name))
        except EngineError as error:
            self.deployments.update(
                deployment, status=Deployment.Status.FAILED, error_code=error.code[:40]
            )
            raise
        self._ready(deployment)
        return name

    def _on_vllm(
        self, engine: Engine, client: EngineClient, base: HubModel, version: ModelVersion
    ) -> str:
        listed: list[Json] = client.models()
        bases: list[str] = [
            str(row["id"])
            for row in listed
            if not row.get("parent") and isinstance(row.get("id"), str)
        ]
        served: str | None = next(
            (name for name in bases if base.repo_id.lower() in {name.lower(), _root(listed, name)}),
            None,
        )
        if served is None and len(bases) == 1 and _root(listed, bases[0]).startswith("/"):
            served = bases[0]
        if served is None:
            raise EngineError(
                "engine_base_mismatch",
                f"vLLM serves {', '.join(bases) or 'nothing'}; this project is built on "
                f"{base.repo_id}.",
            )
        if version.kind != ModelVersion.Kind.LORA:
            return served
        name: str = external_name(version)
        if name not in {str(row.get("id")) for row in listed}:
            deployment: Deployment = self._loading(engine, version, name)
            client.post(
                "/v1/load_lora_adapter", {"lora_name": name, "lora_path": version.storage_dir}
            )
            self._ready(deployment)
        return name

    def _on_ollama(self, engine: Engine, client: EngineClient, version: ModelVersion) -> str:
        name: str = f"mesbah-{external_name(version)}"
        tags: object = client.get("/api/tags").get("models")
        known: set[str] = (
            {str(row.get("name")) for row in tags if isinstance(row, dict)}
            if isinstance(tags, list)
            else set()
        )
        if name in known or f"{name}:latest" in known:
            return name
        gguf: Export | None = self.exports.ready_gguf(version)
        if gguf is None:
            raise EngineError("needs_gguf", "Export this version as GGUF first.")
        deployment: Deployment = self._loading(engine, version, name)
        digest: str = f"sha256:{_sha256(Path(gguf.path))}"
        if not client.has(f"/api/blobs/{digest}"):
            client.upload(f"/api/blobs/{digest}", Path(gguf.path))
        body: Json = {"model": name, "files": {"model.gguf": digest}, "stream": False}
        if version.project.system_prompt:
            body["system"] = version.project.system_prompt
        client.post("/api/create", body)
        self._ready(deployment)
        return name

    def _loading(self, engine: Engine, version: ModelVersion, name: str) -> Deployment:
        existing: Deployment | None = self.deployments.of(engine, version)
        if existing is None:
            return self.deployments.create(
                created_by=self.user if isinstance(self.user, User) else None,
                engine=engine,
                version=version,
                served_name=name,
            )
        return self.deployments.update(existing, status=Deployment.Status.LOADING, error_code="")

    def _ready(self, deployment: Deployment) -> None:
        self.deployments.update(
            deployment, status=Deployment.Status.READY, error_code="", loaded_at=timezone.now()
        )

    def _spec(self, base: HubModel, version: ModelVersion, name: str) -> Json:
        vram: int = self.system.usable_vram_bytes()
        half: int = sizing.chat_bytes(base.parameters or 0, four_bit=False)
        adapters: list[Json] = (
            [{"name": name, "path": version.storage_dir}]
            if name != BASE_NAME and version.storage_dir
            else []
        )
        return {
            "base": base.local_path,
            "architecture": "seq2seq"
            if base.family == HubModel.Family.ENCODER_DECODER
            else "causal",
            "quantize_4bit": vram > 0 and sizing.fit(half, vram).verdict != "fits",
            "gpu_indices": self.system.selected_gpu_indices(),
            "adapters": adapters,
        }


def _serves(state: Json, base_path: str, name: str, adapter_path: str) -> bool:
    if not state.get("loaded") or state.get("base") != base_path:
        return False
    if name == BASE_NAME:
        return True
    adapters: object = state.get("adapters")
    return isinstance(adapters, list) and any(
        isinstance(adapter, dict)
        and adapter.get("name") == name
        and adapter.get("path") == adapter_path
        for adapter in adapters
    )


def _root(listed: list[Json], name: str) -> str:
    for row in listed:
        if row.get("id") == name and isinstance(row.get("root"), str):
            return str(row["root"]).lower()
    return ""


def _sha256(path: Path) -> str:
    digest: hashlib._Hash = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(CHUNK):
            digest.update(block)
    return digest.hexdigest()
