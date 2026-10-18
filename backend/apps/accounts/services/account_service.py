from __future__ import annotations

from typing import Any

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import AnonymousUser, User
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from apps.accounts.repositories import UserRepository

INVALID_CREDENTIALS: str = "That username and password don't match an account."
INACTIVE_ACCOUNT: str = "This account has been deactivated. Contact an administrator."


class AccountService:
    def __init__(self, user: User | AnonymousUser | None = None) -> None:
        self.user: User | AnonymousUser | None = user
        self.users: UserRepository = UserRepository()

    def sign_in(self, request: Request, username: str, password: str) -> User:
        user: User | None = authenticate(request, username=username, password=password)
        if user is None:
            existing: User | None = self.users.find_by_username(username)
            if existing is not None and not existing.is_active:
                raise AuthenticationFailed(INACTIVE_ACCOUNT)
            raise AuthenticationFailed(INVALID_CREDENTIALS)

        login(request, user)
        return user

    def sign_out(self, request: Request) -> None:
        logout(request)

    def identity(self) -> dict[str, Any]:
        if not isinstance(self.user, User) or not self.user.is_authenticated:
            raise AuthenticationFailed(INVALID_CREDENTIALS)

        user: User = self.users.with_groups(self.user.pk) or self.user

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
        if not isinstance(self.user, User) or not self.user.is_authenticated:
            return False
        if self.user.is_superuser:
            return True
        return self.users.in_group(self.user, name)
