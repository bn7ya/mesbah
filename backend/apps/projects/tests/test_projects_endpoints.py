from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.accounts.repositories import UserRepository
from apps.members.roles import TRAINERS, VIEWERS
from apps.models.models import HubModel
from apps.models.repositories import HubModelRepository

if TYPE_CHECKING:
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

PASSWORD: str = "correct-horse-battery-staple"  # noqa: S105


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def member(role: str) -> User:
    users: UserRepository = UserRepository()
    return users.add_to_group(users.create(username=role, password=PASSWORD), role)


def library_model(status: str = HubModel.Status.READY) -> HubModel:
    return HubModelRepository().create(
        repo_id="Qwen/Qwen3-0.6B", status=status, supports_thinking=True, parameters=751_632_384
    )


def new_project(client: APIClient, model: HubModel, name: str = "Support assistant") -> ApiResponse:
    return client.post(
        "/api/projects/",
        {"name": name, "base_model": str(model.pk), "system_prompt": "Answer in Arabic."},
        format="json",
    )


@pytest.mark.django_db
def test_a_trainer_starts_a_project_from_a_downloaded_model(client: APIClient) -> None:
    client.force_login(member(TRAINERS))
    model: HubModel = library_model()

    response: ApiResponse = new_project(client, model)

    assert response.status_code == 201
    body: dict[str, Any] = response.json()
    assert body["slug"] == "support-assistant"
    assert body["kind"] == "finetune"
    assert body["base_model"]["repo_id"] == "Qwen/Qwen3-0.6B"
    assert body["thinking"] is True
    assert body["generation"] == {"temperature": 0.7, "top_p": 0.9, "max_tokens": 1024}
    assert body["active_version"]["number"] == 0
    assert body["active_version"]["name"] == "base"


@pytest.mark.django_db
def test_names_stay_unique_in_their_slug(client: APIClient) -> None:
    client.force_login(member(TRAINERS))
    model: HubModel = library_model()
    new_project(client, model)

    second: dict[str, Any] = new_project(client, model).json()
    arabic: dict[str, Any] = new_project(client, model, name="مساعد الدعم").json()

    assert second["slug"] == "support-assistant-2"
    assert arabic["slug"] == "project"


@pytest.mark.django_db
def test_a_model_still_downloading_cannot_be_used(client: APIClient) -> None:
    client.force_login(member(TRAINERS))

    response: ApiResponse = new_project(client, library_model(HubModel.Status.DOWNLOADING))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "base_model_not_ready"


@pytest.mark.django_db
def test_viewers_read_and_trainers_write(client: APIClient) -> None:
    client.force_login(member(VIEWERS))

    assert client.get("/api/projects/").status_code == 200
    assert new_project(client, library_model()).status_code == 403


@pytest.mark.django_db
def test_changing_and_removing_a_project(client: APIClient) -> None:
    client.force_login(member(TRAINERS))
    project: dict[str, Any] = new_project(client, library_model()).json()

    changed: ApiResponse = client.patch(
        f"/api/projects/{project['id']}/",
        {"name": "Legal helper", "generation": {"temperature": 0.2, "top_p": 1, "max_tokens": 512}},
        format="json",
    )
    removed: ApiResponse = client.delete(f"/api/projects/{project['id']}/")

    assert changed.json()["slug"] == "legal-helper"
    assert changed.json()["generation"]["temperature"] == 0.2
    assert removed.status_code == 204
    assert client.get("/api/projects/").json()["count"] == 0


@pytest.mark.django_db
def test_a_model_a_project_uses_stays_in_the_library(client: APIClient) -> None:
    model: HubModel = library_model()
    client.force_login(member(TRAINERS))
    new_project(client, model)

    response: ApiResponse = client.delete(f"/api/models/{model.pk}/")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "model_in_use"
