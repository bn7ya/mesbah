from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx2
import pytest
from django.contrib.auth.models import AnonymousUser, User
from rest_framework.test import APIClient

from apps.accounts.repositories import UserRepository
from apps.members.roles import ADMINS, TRAINERS
from apps.models.models import HubModel
from apps.models.repositories import HubModelRepository
from apps.projects.models import Project
from apps.projects.repositories import ProjectRepository
from apps.serving.models import Engine
from apps.serving.repositories import EngineRepository
from apps.serving.services import DeploymentService, EngineClient, Target
from apps.serving.services.errors import EngineFailed
from apps.versions.models import Export, ModelVersion
from apps.versions.repositories import ExportRepository, VersionRepository
from apps.versions.services import VersionService

if TYPE_CHECKING:
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

PASSWORD: str = "correct-horse-battery-staple"  # noqa: S105


class Server:
    def __init__(self, routes: dict[str, httpx2.Response]) -> None:
        self.routes: dict[str, httpx2.Response] = routes
        self.seen: list[tuple[str, str, bytes]] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.seen.append((request.method, request.url.path, request.read()))
        key: str = f"{request.method} {request.url.path}"
        return self.routes.get(key, httpx2.Response(404))


@pytest.fixture
def admin(db: None) -> User:
    users: UserRepository = UserRepository()
    return users.add_to_group(users.create(username="sara", password=PASSWORD), ADMINS)


@pytest.fixture
def version(admin: User, tmp_path: Path) -> ModelVersion:
    model: HubModel = HubModelRepository().create(
        repo_id="Qwen/Qwen3-0.6B", status=HubModel.Status.READY, local_path="/models/qwen"
    )
    project: Project = ProjectRepository().create(
        name="Support", slug="support", base_model=model, system_prompt="Be kind."
    )
    versions: VersionService = VersionService(admin)
    root: ModelVersion = versions.create_root(project)
    return VersionRepository().create(
        project=project,
        parent=root,
        number=1,
        kind=ModelVersion.Kind.LORA,
        storage_dir=str(tmp_path / "v1"),
    )


@pytest.fixture
def served() -> Iterator[None]:
    yield
    EngineClient.transport = None


def engine(kind: str, **fields: Any) -> Engine:
    return EngineRepository().create(
        name=kind, kind=kind, base_url="http://engine.test:8000", **fields
    )


@pytest.mark.django_db
def test_vllm_loads_the_version_as_a_lora(version: ModelVersion, served: None) -> None:
    server: Server = Server(
        {
            "GET /v1/models": httpx2.Response(
                200, json={"data": [{"id": "qwen", "root": "Qwen/Qwen3-0.6B"}]}
            ),
            "POST /v1/load_lora_adapter": httpx2.Response(200, text="Success"),
        }
    )
    EngineClient.transport = httpx2.MockTransport(server)

    target: Target = DeploymentService(AnonymousUser()).target(version, engine("vllm"))

    assert target.model == "support-v1"
    loaded: dict[str, str] = json.loads(server.seen[-1][2])
    assert loaded == {"lora_name": "support-v1", "lora_path": version.storage_dir}


@pytest.mark.django_db
def test_vllm_serving_another_model_is_named(version: ModelVersion, served: None) -> None:
    server: Server = Server(
        {"GET /v1/models": httpx2.Response(200, json={"data": [{"id": "llama", "root": "x/y"}]})}
    )
    EngineClient.transport = httpx2.MockTransport(server)

    with pytest.raises(EngineFailed) as raised:
        DeploymentService(AnonymousUser()).target(version, engine("vllm"))

    assert raised.value.default_code == "engine_base_mismatch"


@pytest.mark.django_db
def test_ollama_needs_a_gguf_export(version: ModelVersion, served: None) -> None:
    EngineClient.transport = httpx2.MockTransport(
        Server({"GET /api/tags": httpx2.Response(200, json={"models": []})})
    )

    with pytest.raises(EngineFailed) as raised:
        DeploymentService(AnonymousUser()).target(version, engine("ollama"))

    assert raised.value.default_code == "needs_gguf"


@pytest.mark.django_db
def test_ollama_imports_the_gguf(version: ModelVersion, served: None, tmp_path: Path) -> None:
    gguf: Path = tmp_path / "model.gguf"
    gguf.write_bytes(b"GGUF")
    ExportRepository().create(
        version=version, format=Export.Format.GGUF, status=Export.Status.READY, path=str(gguf)
    )
    digest: str = f"sha256:{hashlib.sha256(b'GGUF').hexdigest()}"
    server: Server = Server(
        {
            "GET /api/tags": httpx2.Response(200, json={"models": []}),
            f"HEAD /api/blobs/{digest}": httpx2.Response(404),
            f"POST /api/blobs/{digest}": httpx2.Response(201),
            "POST /api/create": httpx2.Response(200, json={"status": "success"}),
        }
    )
    EngineClient.transport = httpx2.MockTransport(server)

    target: Target = DeploymentService(AnonymousUser()).target(version, engine("ollama"))

    assert target.model == "mesbah-support-v1"
    assert ("POST", f"/api/blobs/{digest}", b"GGUF") in server.seen
    body: dict[str, Any] = json.loads(server.seen[-1][2])
    assert body["files"] == {"model.gguf": digest}
    assert body["system"] == "Be kind."


@pytest.mark.django_db
def test_an_openai_compatible_server_answers_with_its_own_model(
    version: ModelVersion, served: None
) -> None:
    target: Target = DeploymentService(AnonymousUser()).target(
        version, engine("openai", model_name="gpt-oss-20b")
    )

    assert target.model == "gpt-oss-20b"


@pytest.mark.django_db
def test_administrators_connect_engines_and_trainers_cannot(admin: User, served: None) -> None:
    EngineClient.transport = httpx2.MockTransport(
        Server({"GET /v1/models": httpx2.Response(200, json={"data": [{"id": "m"}]})})
    )
    api: APIClient = APIClient()
    api.force_login(admin)
    body: dict[str, Any] = {
        "name": "GPU box",
        "kind": "vllm",
        "base_url": "http://gpu-box:8000",
        "api_key": "secret",
        "is_default": True,
    }

    created: ApiResponse = api.post("/api/serving/engines/", body, format="json")

    assert created.status_code == 201
    assert created.json()["has_api_key"] is True
    assert "api_key" not in created.json()
    assert created.json()["state"]["running"] is True
    defaults: list[str] = [
        row["name"]
        for row in api.get("/api/serving/engines/").json()["results"]
        if row["is_default"]
    ]
    assert defaults == ["GPU box"]
    users: UserRepository = UserRepository()
    trainer: User = users.add_to_group(users.create(username="tariq", password=PASSWORD), TRAINERS)
    api.force_login(trainer)
    assert api.post("/api/serving/engines/", body, format="json").status_code == 403


@pytest.mark.django_db
def test_the_builtin_engine_stays(admin: User) -> None:
    builtin: Engine | None = EngineRepository().builtin()
    assert builtin is not None
    api: APIClient = APIClient()
    api.force_login(admin)

    response: ApiResponse = api.delete(f"/api/serving/engines/{builtin.pk}/")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "builtin_engine_kept"
