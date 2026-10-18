from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any

import httpx2
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.accounts.repositories import UserRepository
from apps.members.roles import TRAINERS, VIEWERS
from apps.models.models import HubModel
from apps.models.repositories import HubModelRepository
from apps.projects.models import Project
from apps.projects.repositories import ProjectRepository
from apps.serving.models import Engine
from apps.serving.repositories import EngineRepository
from apps.serving.services import DeploymentService, EngineClient, Target
from apps.versions.models import ModelVersion
from apps.versions.repositories import VersionRepository

if TYPE_CHECKING:
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

PASSWORD: str = "correct-horse-battery-staple"  # noqa: S105

type Handler = Callable[[httpx2.Request], httpx2.Response]


class FakeRuntime:
    def __init__(self) -> None:
        self.loaded: dict[str, Any] | None = None
        self.calls: list[str] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.calls.append(f"{request.method} {request.url.path}")
        if request.url.path == "/admin/status":
            if self.loaded is None:
                return httpx2.Response(200, json={"loaded": False, "busy": False})
            return httpx2.Response(
                200, json={"loaded": True, "busy": False, "device": "cpu", **self.loaded}
            )
        if request.url.path == "/admin/load":
            body: dict[str, Any] = json.loads(request.content)
            self.loaded = {"base": body["base"], "adapters": body["adapters"]}
            return httpx2.Response(200, json={"loaded": True})
        if request.url.path == "/admin/unload":
            self.loaded = None
            return httpx2.Response(200, json={"loaded": False})
        return httpx2.Response(404)


@pytest.fixture
def runtime() -> Iterator[FakeRuntime]:
    fake: FakeRuntime = FakeRuntime()
    EngineClient.transport = httpx2.MockTransport(fake)
    yield fake
    EngineClient.transport = None


@pytest.fixture
def stopped() -> Iterator[None]:
    def refuse(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("refused", request=request)

    EngineClient.transport = httpx2.MockTransport(refuse)
    yield
    EngineClient.transport = None


@pytest.fixture
def trainer(db: None) -> User:
    users: UserRepository = UserRepository()
    return users.add_to_group(users.create(username="tariq", password=PASSWORD), TRAINERS)


@pytest.fixture
def version(trainer: User) -> ModelVersion:
    model: HubModel = HubModelRepository().create(
        repo_id="org/tiny",
        status=HubModel.Status.READY,
        local_path="/models/org-tiny",
        parameters=1_000_000,
    )
    project: Project = ProjectRepository().create(name="Tiny", slug="tiny", base_model=model)
    root: ModelVersion = VersionRepository().create(
        project=project, number=0, kind=ModelVersion.Kind.BASE, name="base"
    )
    return VersionRepository().create(
        project=project,
        parent=root,
        number=1,
        kind=ModelVersion.Kind.LORA,
        storage_dir="/versions/v1",
    )


def builtin() -> Engine:
    engine: Engine | None = EngineRepository().builtin()
    assert engine is not None
    return engine


@pytest.mark.django_db
def test_the_builtin_engine_exists_and_is_the_default() -> None:
    engine: Engine = builtin()

    assert engine.is_default is True


@pytest.mark.django_db
def test_a_stopped_engine_shows_as_not_running(trainer: User, stopped: None) -> None:
    client: APIClient = APIClient()
    client.force_login(trainer)

    response: ApiResponse = client.get("/api/serving/engines/")

    row: dict[str, Any] = response.json()["results"][0]
    assert row["kind"] == "builtin"
    assert row["state"]["running"] is False
    assert row["state"]["loaded"] is False


@pytest.mark.django_db
def test_a_version_loads_once_and_shows_on_the_engine(
    trainer: User, version: ModelVersion, runtime: FakeRuntime
) -> None:
    service: DeploymentService = DeploymentService(trainer)

    target: Target = service.target(version)
    service.target(version)

    assert target.model == str(version.pk)
    assert runtime.calls.count("POST /admin/load") == 1
    assert runtime.loaded is not None
    assert runtime.loaded["adapters"] == [{"name": str(version.pk), "path": "/versions/v1"}]
    client: APIClient = APIClient()
    client.force_login(trainer)
    state: dict[str, Any] = client.get(f"/api/serving/engines/{builtin().pk}/").json()["state"]
    assert state["base_model"]["repo_id"] == "org/tiny"
    assert [loaded["id"] for loaded in state["versions"]] == [str(version.pk)]


@pytest.mark.django_db
def test_unloading_frees_the_engine(
    trainer: User, version: ModelVersion, runtime: FakeRuntime
) -> None:
    DeploymentService(trainer).target(version)
    client: APIClient = APIClient()
    client.force_login(trainer)

    response: ApiResponse = client.post(f"/api/serving/engines/{builtin().pk}/unload/")

    assert response.status_code == 200
    assert response.json()["state"]["loaded"] is False


@pytest.mark.django_db
def test_viewers_see_engines_but_cannot_unload(runtime: FakeRuntime) -> None:
    users: UserRepository = UserRepository()
    viewer: User = users.add_to_group(users.create(username="noor", password=PASSWORD), VIEWERS)
    client: APIClient = APIClient()
    client.force_login(viewer)

    assert client.get("/api/serving/engines/").status_code == 200
    assert client.post(f"/api/serving/engines/{builtin().pk}/unload/").status_code == 403
