"""The auth slice, from the outside.

Setup goes through `UserRepository` rather than the ORM directly — going
through the repository is also how the rest of the codebase would create a
user.
"""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.repositories import UserRepository

PASSWORD = "correct-horse-battery-staple"  # noqa: S105

# A refused sign-in answers 403, not 401.
#
# DRF downgrades AuthenticationFailed to 403 when no authenticator can produce
# a `WWW-Authenticate` challenge, and cookie auth has no challenge scheme to
# offer. RFC 9110 requires that header on a 401, so 403 is the honest answer
# here — the reason is in the body, where `code` is still
# `authentication_failed`.
REFUSED = 403


@pytest.fixture
def users() -> UserRepository:
    return UserRepository()


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def member(db, users):
    user = users.create(username="sara", password=PASSWORD, email="sara@example.com")
    users.add_to_group(user, "members")
    return user


@pytest.mark.django_db
def test_me_requires_authentication(client):
    response = client.get("/api/auth/me/")

    assert response.status_code == 403
    assert "error" in response.json()


@pytest.mark.django_db
def test_sign_in_returns_identity_with_group_names(client, member):
    response = client.post(
        "/api/auth/login/",
        {"username": "sara", "password": PASSWORD},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "sara"
    # This list is what the frontend's route guards would read.
    assert body["groups"] == ["members"]


@pytest.mark.django_db
def test_sign_in_with_a_wrong_password_says_nothing_useful(client, member):
    response = client.post(
        "/api/auth/login/",
        {"username": "sara", "password": "wrong"},
    )

    assert response.status_code == REFUSED
    message = response.json()["error"]["message"]
    # The same message an unknown username gets — otherwise this endpoint
    # enumerates accounts.
    assert "don't match" in message


@pytest.mark.django_db
def test_sign_in_with_an_unknown_username_says_the_same_thing(client, db):
    response = client.post(
        "/api/auth/login/",
        {"username": "nobody", "password": PASSWORD},
    )

    assert response.status_code == REFUSED
    assert "don't match" in response.json()["error"]["message"]


@pytest.mark.django_db
def test_deactivated_account_gets_its_own_message(client, member, users):
    users.deactivate(member)

    response = client.post(
        "/api/auth/login/",
        {"username": "sara", "password": PASSWORD},
    )

    assert response.status_code == REFUSED
    assert "deactivated" in response.json()["error"]["message"]


@pytest.mark.django_db
def test_me_reports_permissions_inherited_from_groups(client, member, users):
    users.grant_to_group(users.ensure_group("members"), "add_group")

    client.force_login(member)
    response = client.get("/api/auth/me/")

    assert response.status_code == 200
    assert "auth.add_group" in response.json()["permissions"]


@pytest.mark.django_db
def test_sign_out_ends_the_session(client, member):
    client.force_login(member)

    assert client.post("/api/auth/logout/").status_code == 204
    assert client.get("/api/auth/me/").status_code == 403


@pytest.mark.django_db
def test_health_is_public(client):
    response = client.get("/api/health/")

    assert response.status_code == 200
    assert response.json()["checks"]["database"] is True
