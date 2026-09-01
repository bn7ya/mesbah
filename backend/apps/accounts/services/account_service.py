"""Session lifecycle and identity. Rules live here; the ORM does not."""
from __future__ import annotations

from typing import Any

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from apps.accounts.repositories import UserRepository

INVALID_CREDENTIALS = "That username and password don't match an account."
INACTIVE_ACCOUNT = "This account has been deactivated. Contact an administrator."


class AccountService:
    """Takes the acting user, like every service in this project.

    On the sign-in path there is no acting user yet, so it is `None` — the
    one case where it may be.
    """

    def __init__(self, user: User | None = None) -> None:
        self.user = user
        self.users = UserRepository()

    # ------------------------------------------------------------ sessions

    def sign_in(self, request: Request, username: str, password: str) -> User:
        """Authenticate and start a session.

        The same message for a wrong password and an unknown username, on
        purpose: distinguishing them tells an attacker which usernames exist.
        """
        user = authenticate(request, username=username, password=password)
        if user is None:
            existing = self.users.find_by_username(username)
            if existing is not None and not existing.is_active:
                raise AuthenticationFailed(INACTIVE_ACCOUNT)
            raise AuthenticationFailed(INVALID_CREDENTIALS)

        login(request, user)
        return user

    def sign_out(self, request: Request) -> None:
        """End the session. Idempotent — signing out twice is not an error."""
        logout(request)

    # ------------------------------------------------------------ identity

    def identity(self) -> dict[str, Any]:
        """What `/api/auth/me/` returns.

        Groups are the authorization system. The frontend reads these names
        for its guards and for showing or hiding affordances — a convenience
        only; the backend's `permission_classes` is the security boundary.
        """
        if self.user is None or not self.user.is_authenticated:
            raise AuthenticationFailed(INVALID_CREDENTIALS)

        user = self.users.with_groups(self.user.pk) or self.user

        return {
            "id": user.pk,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "groups": self.users.group_names(user),
            "permissions": self.users.permission_codenames(user),
        }

    def has_group(self, name: str) -> bool:
        if self.user is None or not self.user.is_authenticated:
            return False
        if self.user.is_superuser:
            return True
        return self.users.in_group(self.user, name)
