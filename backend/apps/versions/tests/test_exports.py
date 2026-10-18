from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest
from django.contrib.auth.models import User
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from apps.accounts.repositories import UserRepository
from apps.members.roles import TRAINERS
from apps.models.models import HubModel
from apps.models.repositories import HubModelRepository
from apps.projects.models import Project
from apps.projects.repositories import ProjectRepository
from apps.versions.models import ModelVersion
from apps.versions.repositories import VersionRepository
from apps.versions.services import ExportService, VersionService

if TYPE_CHECKING:
    from django.http import FileResponse
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

PASSWORD: str = "correct-horse-battery-staple"  # noqa: S105


@pytest.fixture(autouse=True)
def data_dir(settings: Settings, tmp_path: Path) -> Path:
    settings.MESBAH_DATA_DIR = tmp_path
    return tmp_path


@pytest.fixture
def trainer(db: None) -> User:
    users: UserRepository = UserRepository()
    return users.add_to_group(users.create(username="tariq", password=PASSWORD), TRAINERS)


@pytest.fixture
def client(trainer: User) -> APIClient:
    api: APIClient = APIClient()
    api.force_login(trainer)
    return api


@pytest.fixture
def trained(trainer: User, data_dir: Path) -> ModelVersion:
    model: HubModel = HubModelRepository().create(
        repo_id="org/tiny", status=HubModel.Status.READY, local_path=str(data_dir / "base")
    )
    project: Project = ProjectRepository().create(name="Tiny", slug="tiny", base_model=model)
    versions: VersionService = VersionService(trainer)
    root: ModelVersion = versions.create_root(project)
    adapter: Path = data_dir / "versions" / "v1"
    adapter.mkdir(parents=True)
    (adapter / "adapter_config.json").write_text("{}")
    (adapter / "adapter_model.safetensors").write_bytes(b"\0" * 64)
    return VersionRepository().create(
        project=project,
        parent=root,
        number=1,
        kind=ModelVersion.Kind.LORA,
        storage_dir=str(adapter),
    )


def export(client: APIClient, version: ModelVersion, **body: str) -> ApiResponse:
    return client.post(f"/api/versions/{version.pk}/exports/", body, format="json")


@pytest.mark.django_db
def test_a_lora_export_is_a_zip_with_instructions(
    client: APIClient, trainer: User, trained: ModelVersion
) -> None:
    queued: ApiResponse = export(client, trained, format="lora")
    ExportService(trainer).run(queued.json()["id"])

    shown: dict[str, Any] = client.get(f"/api/versions/exports/{queued.json()['id']}/").json()
    download: FileResponse = cast(
        "FileResponse", client.get(f"/api/versions/exports/{shown['id']}/download/")
    )

    assert queued.status_code == 202
    assert shown["status"] == "ready"
    assert shown["downloadable"] is True
    archive: zipfile.ZipFile = zipfile.ZipFile(BytesIO(download.getvalue()))
    assert sorted(archive.namelist()) == [
        "README.md",
        "adapter_config.json",
        "adapter_model.safetensors",
    ]
    assert "vllm serve org/tiny" in archive.read("README.md").decode()
    assert download["Content-Disposition"].endswith('tiny-v1-lora.zip"')


@pytest.mark.django_db
def test_the_base_has_no_change_to_export_as_a_lora(
    client: APIClient, trained: ModelVersion
) -> None:
    assert trained.parent is not None

    response: ApiResponse = export(client, trained.parent, format="lora")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_exportable"


@pytest.mark.django_db
def test_a_gguf_export_needs_the_training_parts(
    client: APIClient, trainer: User, trained: ModelVersion, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("mesbah.parts.installed", lambda name: None)
    queued: ApiResponse = export(client, trained, format="gguf", out_type="q8_0")

    ExportService(trainer).run(queued.json()["id"])

    shown: dict[str, Any] = client.get(f"/api/versions/exports/{queued.json()['id']}/").json()
    assert shown["out_type"] == "q8_0"
    assert shown["status"] == "failed"
    assert shown["error_code"] == "training_parts_missing"


@pytest.mark.django_db
def test_removing_an_export_deletes_its_files(
    client: APIClient, trainer: User, trained: ModelVersion, data_dir: Path
) -> None:
    queued: ApiResponse = export(client, trained, format="lora")
    ExportService(trainer).run(queued.json()["id"])

    response: ApiResponse = client.delete(f"/api/versions/exports/{queued.json()['id']}/")

    assert response.status_code == 204
    assert not (data_dir / "exports" / queued.json()["id"]).exists()
    assert client.get(f"/api/versions/{trained.pk}/exports/").json()["count"] == 0


@pytest.mark.django_db
def test_what_changed_is_a_grid_of_layers_and_modules(
    client: APIClient, trained: ModelVersion
) -> None:
    trained.delta_stats = {
        "total_norm": 0.5,
        "parameters": 1024,
        "rank": 16,
        "change_from_parent": None,
        "layers": [
            {"name": "a", "layer": 1, "module": "q_proj", "norm": 0.2},
            {"name": "b", "layer": 0, "module": "v_proj", "norm": 0.1},
            {"name": "c", "layer": 0, "module": "q_proj", "norm": 0.3},
        ],
    }
    trained.save()

    body: dict[str, Any] = client.get(f"/api/versions/{trained.pk}/changes/").json()

    assert body["modules"] == ["q_proj", "v_proj"]
    assert body["layers"] == [
        {"layer": 0, "norms": {"v_proj": 0.1, "q_proj": 0.3}},
        {"layer": 1, "norms": {"q_proj": 0.2}},
    ]
    assert body["rank"] == 16
