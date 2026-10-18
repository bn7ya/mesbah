from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.accounts.repositories import UserRepository
from apps.members.roles import ADMINS, REVIEWERS, TRAINERS, VIEWERS, at_least, highest

if TYPE_CHECKING:
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

PASSWORD: str = "correct-horse-battery-staple"  # noqa: S105


@pytest.fixture
def users() -> UserRepository:
    return UserRepository()


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def admin(db: None, users: UserRepository) -> User:
    return users.add_to_group(users.create(username="amal", password=PASSWORD), ADMINS)


@pytest.fixture
def trainer(db: None, users: UserRepository) -> User:
    return users.add_to_group(users.create(username="tariq", password=PASSWORD), TRAINERS)


def test_the_role_ladder() -> None:
    assert highest(["viewers", "trainers"]) == TRAINERS
    assert highest([]) is None
    assert highest([], superuser=True) == ADMINS
    assert at_least(REVIEWERS) == (REVIEWERS, TRAINERS, ADMINS)


@pytest.mark.django_db
def test_the_four_roles_exist_after_migrating(users: UserRepository) -> None:
    for role in (VIEWERS, REVIEWERS, TRAINERS, ADMINS):
        assert users.ensure_group(role).name == role


@pytest.mark.django_db
def test_only_administrators_see_members(client: APIClient, trainer: User) -> None:
    client.force_login(trainer)

    assert client.get("/api/members/").status_code == 403


@pytest.mark.django_db
def test_members_are_listed_with_their_role(client: APIClient, admin: User, trainer: User) -> None:
    client.force_login(admin)

    response: ApiResponse = client.get("/api/members/")

    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    assert body["count"] == 2
    roles: dict[str, str] = {row["username"]: row["role"] for row in body["results"]}
    assert roles == {"amal": ADMINS, "tariq": TRAINERS}
    assert [row["is_self"] for row in body["results"]] == [True, False]


@pytest.mark.django_db
def test_an_administrator_adds_a_reviewer(client: APIClient, admin: User) -> None:
    client.force_login(admin)

    response: ApiResponse = client.post(
        "/api/members/",
        {"username": "rana", "password": PASSWORD, "role": REVIEWERS, "first_name": "Rana"},
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["role"] == REVIEWERS
    assert client.login(username="rana", password=PASSWORD)


@pytest.mark.django_db
def test_a_username_is_used_once(client: APIClient, admin: User, trainer: User) -> None:
    client.force_login(admin)

    response: ApiResponse = client.post(
        "/api/members/",
        {"username": "TARIQ", "password": PASSWORD, "role": VIEWERS},
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "username_taken"


@pytest.mark.django_db
def test_a_weak_password_is_refused(client: APIClient, admin: User) -> None:
    client.force_login(admin)

    response: ApiResponse = client.post(
        "/api/members/",
        {"username": "rana", "password": "12345678", "role": VIEWERS},
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "weak_password"


@pytest.mark.django_db
def test_changing_a_role_replaces_the_old_one(
    client: APIClient, admin: User, trainer: User, users: UserRepository
) -> None:
    client.force_login(admin)

    response: ApiResponse = client.patch(
        f"/api/members/{trainer.pk}/", {"role": VIEWERS}, format="json"
    )

    assert response.status_code == 200
    assert users.group_names(trainer) == [VIEWERS]


@pytest.mark.django_db
def test_the_last_administrator_stays(client: APIClient, admin: User) -> None:
    client.force_login(admin)

    demote: ApiResponse = client.patch(
        f"/api/members/{admin.pk}/", {"role": TRAINERS}, format="json"
    )

    assert demote.status_code == 409
    assert demote.json()["error"]["code"] == "last_administrator"


@pytest.mark.django_db
def test_nobody_deactivates_themselves(
    client: APIClient, admin: User, users: UserRepository
) -> None:
    users.add_to_group(users.create(username="second", password=PASSWORD), ADMINS)
    client.force_login(admin)

    response: ApiResponse = client.patch(
        f"/api/members/{admin.pk}/", {"is_active": False}, format="json"
    )

    assert response.json()["error"]["code"] == "self_deactivation"


@pytest.mark.django_db
def test_a_deactivated_member_cannot_sign_in(client: APIClient, admin: User, trainer: User) -> None:
    client.force_login(admin)

    response: ApiResponse = client.patch(
        f"/api/members/{trainer.pk}/", {"is_active": False}, format="json"
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert not APIClient().login(username="tariq", password=PASSWORD)


@pytest.mark.django_db
def test_the_owner_keeps_its_role(client: APIClient, admin: User, users: UserRepository) -> None:
    owner: User = users.create(username="owner", password=PASSWORD, is_superuser=True)
    client.force_login(admin)

    response: ApiResponse = client.patch(
        f"/api/members/{owner.pk}/", {"role": VIEWERS}, format="json"
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "owner_locked"


@pytest.mark.django_db
def test_an_unknown_member_is_not_found(client: APIClient, admin: User) -> None:
    client.force_login(admin)

    assert client.patch("/api/members/9999/", {"role": VIEWERS}, format="json").status_code == 404
