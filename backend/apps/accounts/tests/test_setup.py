from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from django.conf import LazySettings
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.repositories import UserRepository
from apps.accounts.services.setup_code import code_path

if TYPE_CHECKING:
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

PASSWORD: str = "correct-horse-battery-staple"  # noqa: S105


@pytest.fixture(autouse=True)
def data_dir(settings: LazySettings, tmp_path: Path) -> None:
    settings.MESBAH_DATA_DIR = tmp_path


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def owner_payload(code: str, **overrides: str) -> dict[str, str]:
    return {"code": code, "username": "owner", "password": PASSWORD, **overrides}


@pytest.mark.django_db
def test_a_fresh_install_needs_setup_and_keeps_a_code(client: APIClient) -> None:
    response: ApiResponse = client.get("/api/auth/setup/")

    assert response.json() == {"needed": True}
    assert len(code_path().read_text().replace("-", "")) == 12
    assert code_path().stat().st_mode & 0o777 == 0o600


@pytest.mark.django_db
def test_the_code_is_stable_until_it_is_used(client: APIClient) -> None:
    client.get("/api/auth/setup/")
    first: str = code_path().read_text()

    client.get("/api/auth/setup/")

    assert code_path().read_text() == first


@pytest.mark.django_db
def test_a_wrong_code_is_refused(client: APIClient) -> None:
    client.get("/api/auth/setup/")

    response: ApiResponse = client.post(
        "/api/auth/setup/", owner_payload("AAAA-BBBB-CCCC"), format="json"
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "setup_code_rejected"
    assert not UserRepository().any_exists()


@pytest.mark.django_db
def test_setup_creates_the_owner_and_signs_them_in(client: APIClient) -> None:
    client.get("/api/auth/setup/")
    code: str = code_path().read_text().lower()

    response: ApiResponse = client.post("/api/auth/setup/", owner_payload(code), format="json")

    assert response.status_code == 201
    body: dict[str, Any] = response.json()
    assert body["username"] == "owner"
    assert body["is_superuser"] is True
    assert body["groups"] == ["admins"]
    assert client.get("/api/auth/me/").status_code == 200
    assert not code_path().exists()
    assert client.get("/api/auth/setup/").json() == {"needed": False}


@pytest.mark.django_db
def test_setup_happens_once(client: APIClient) -> None:
    client.get("/api/auth/setup/")
    code: str = code_path().read_text()
    client.post("/api/auth/setup/", owner_payload(code), format="json")

    response: ApiResponse = APIClient().post(
        "/api/auth/setup/", owner_payload(code, username="intruder"), format="json"
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "setup_done"


@pytest.mark.django_db
def test_a_weak_owner_password_is_refused(client: APIClient) -> None:
    client.get("/api/auth/setup/")

    response: ApiResponse = client.post(
        "/api/auth/setup/",
        owner_payload(code_path().read_text(), password="password"),
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "weak_password"
    assert code_path().exists()


@pytest.mark.django_db
def test_the_command_prints_the_code(capsys: pytest.CaptureFixture[str]) -> None:
    call_command("setup_code")

    assert capsys.readouterr().out.strip() == code_path().read_text()
