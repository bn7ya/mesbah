from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.accounts.repositories import UserRepository

if TYPE_CHECKING:
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

PASSWORD: str = "correct-horse-battery-staple"  # noqa: S105

REFUSED: int = 403


@pytest.fixture
def users() -> UserRepository:
    return UserRepository()


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def member(db: None, users: UserRepository) -> User:
    user: User = users.create(username="sara", password=PASSWORD, email="sara@example.com")
    users.add_to_group(user, "members")
    return user


@pytest.mark.django_db
def test_me_requires_authentication(client: APIClient) -> None:
    response: ApiResponse = client.get("/api/auth/me/")

    assert response.status_code == 403
    assert "error" in response.json()


@pytest.mark.django_db
def test_sign_in_returns_identity_with_group_names(client: APIClient, member: User) -> None:
    response: ApiResponse = client.post(
        "/api/auth/login/",
        {"username": "sara", "password": PASSWORD},
    )

    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    assert body["username"] == "sara"
    assert body["groups"] == ["members"]


@pytest.mark.django_db
def test_sign_in_with_a_wrong_password_says_nothing_useful(client: APIClient, member: User) -> None:
    response: ApiResponse = client.post(
        "/api/auth/login/",
        {"username": "sara", "password": "wrong"},
    )

    assert response.status_code == REFUSED
    message: str = response.json()["error"]["message"]
    assert "don't match" in message


@pytest.mark.django_db
def test_sign_in_with_an_unknown_username_says_the_same_thing(client: APIClient, db: None) -> None:
    response: ApiResponse = client.post(
        "/api/auth/login/",
        {"username": "nobody", "password": PASSWORD},
    )

    assert response.status_code == REFUSED
    assert "don't match" in response.json()["error"]["message"]


@pytest.mark.django_db
def test_deactivated_account_gets_its_own_message(
    client: APIClient, member: User, users: UserRepository
) -> None:
    users.deactivate(member)

    response: ApiResponse = client.post(
        "/api/auth/login/",
        {"username": "sara", "password": PASSWORD},
    )

    assert response.status_code == REFUSED
    assert "deactivated" in response.json()["error"]["message"]


@pytest.mark.django_db
def test_me_reports_permissions_inherited_from_groups(
    client: APIClient, member: User, users: UserRepository
) -> None:
    users.grant_to_group(users.ensure_group("members"), "add_group")

    client.force_login(member)
    response: ApiResponse = client.get("/api/auth/me/")

    assert response.status_code == 200
    assert "auth.add_group" in response.json()["permissions"]


@pytest.mark.django_db
def test_sign_out_ends_the_session(client: APIClient, member: User) -> None:
    client.force_login(member)

    assert client.post("/api/auth/logout/").status_code == 204
    assert client.get("/api/auth/me/").status_code == 403


@pytest.mark.django_db
def test_health_is_public(client: APIClient) -> None:
    response: ApiResponse = client.get("/api/health/")

    assert response.status_code == 200
    assert response.json()["checks"]["database"] is True
