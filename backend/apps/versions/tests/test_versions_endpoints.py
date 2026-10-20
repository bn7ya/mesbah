from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.accounts.repositories import UserRepository
from apps.members.roles import TRAINERS, VIEWERS
from apps.models.models import HubModel
from apps.models.repositories import HubModelRepository
from apps.projects.models import Project
from apps.projects.repositories import ProjectRepository
from apps.versions.models import ModelVersion
from apps.versions.repositories import VersionRepository

if TYPE_CHECKING:
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

PASSWORD: str = "correct-horse-battery-staple"  # noqa: S105


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def trainer(db: None) -> User:
    users: UserRepository = UserRepository()
    return users.add_to_group(users.create(username="tariq", password=PASSWORD), TRAINERS)


@pytest.fixture
def project(client: APIClient, trainer: User) -> dict[str, Any]:
    model: HubModel = HubModelRepository().create(
        repo_id="org/tiny", status=HubModel.Status.READY, size_bytes=8_000_000
    )
    client.force_login(trainer)
    created: ApiResponse = client.post(
        "/api/projects/", {"name": "Tiny", "base_model": str(model.pk)}, format="json"
    )
    body: dict[str, Any] = created.json()
    return body


def child(project_id: str, parent: ModelVersion, number: int) -> ModelVersion:
    owner: Project | None = ProjectRepository().find(project_id)
    assert owner is not None
    return VersionRepository().create(
        project=owner, parent=parent, number=number, kind=ModelVersion.Kind.LORA, lora_rank=16
    )


def tree(client: APIClient, project_id: str) -> list[dict[str, Any]]:
    response: ApiResponse = client.get("/api/versions/", {"project": project_id})
    rows: list[dict[str, Any]] = response.json()["results"]
    return rows


@pytest.mark.django_db
def test_a_new_project_starts_at_its_base(client: APIClient, project: dict[str, Any]) -> None:
    versions: list[dict[str, Any]] = tree(client, project["id"])

    assert len(versions) == 1
    assert versions[0]["kind"] == "base"
    assert versions[0]["name"] == "base"
    assert versions[0]["is_active"] is True
    assert versions[0]["parent_id"] is None
    assert versions[0]["full_size_bytes"] == 8_000_000


@pytest.mark.django_db
def test_activating_an_older_version_rolls_back(client: APIClient, project: dict[str, Any]) -> None:
    root: ModelVersion | None = VersionRepository().root_of(project["id"])
    assert root is not None
    first: ModelVersion = child(project["id"], root, 1)
    second: ModelVersion = child(project["id"], first, 2)
    client.post(f"/api/versions/{second.pk}/activate/")

    response: ApiResponse = client.post(f"/api/versions/{first.pk}/activate/")

    assert response.json()["is_active"] is True
    active: list[str] = [row["name"] for row in tree(client, project["id"]) if row["is_active"]]
    assert active == ["v1"]


@pytest.mark.django_db
def test_the_base_and_the_active_version_stay(client: APIClient, project: dict[str, Any]) -> None:
    root: ModelVersion | None = VersionRepository().root_of(project["id"])
    assert root is not None
    first: ModelVersion = child(project["id"], root, 1)
    client.post(f"/api/versions/{first.pk}/activate/")

    assert client.delete(f"/api/versions/{root.pk}/").json()["error"]["code"] == "root_version_kept"
    assert (
        client.delete(f"/api/versions/{first.pk}/").json()["error"]["code"] == "active_version_kept"
    )


@pytest.mark.django_db
def test_removing_a_version_moves_its_children_up(
    client: APIClient, project: dict[str, Any]
) -> None:
    root: ModelVersion | None = VersionRepository().root_of(project["id"])
    assert root is not None
    first: ModelVersion = child(project["id"], root, 1)
    second: ModelVersion = child(project["id"], first, 2)

    response: ApiResponse = client.delete(f"/api/versions/{first.pk}/")

    assert response.status_code == 204
    rows: dict[str, dict[str, Any]] = {row["name"]: row for row in tree(client, project["id"])}
    assert set(rows) == {"base", "v2"}
    assert rows["v2"]["parent_id"] == str(root.pk)
    assert second.pk


@pytest.mark.django_db
def test_renaming_a_version(client: APIClient, project: dict[str, Any]) -> None:
    root: ModelVersion | None = VersionRepository().root_of(project["id"])
    assert root is not None
    first: ModelVersion = child(project["id"], root, 1)

    response: ApiResponse = client.patch(
        f"/api/versions/{first.pk}/",
        {"name": "Polite replies", "notes": "Fewer apologies."},
        format="json",
    )

    assert response.json()["name"] == "Polite replies"


@pytest.mark.django_db
def test_viewers_cannot_activate(client: APIClient, project: dict[str, Any]) -> None:
    users: UserRepository = UserRepository()
    viewer: User = users.add_to_group(users.create(username="noor", password=PASSWORD), VIEWERS)
    root: ModelVersion | None = VersionRepository().root_of(project["id"])
    assert root is not None
    client.force_login(viewer)

    assert client.get("/api/versions/", {"project": project["id"]}).status_code == 200
    assert client.post(f"/api/versions/{root.pk}/activate/").status_code == 403
