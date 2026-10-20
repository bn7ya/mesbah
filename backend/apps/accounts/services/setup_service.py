from __future__ import annotations

from typing import Any

from django.contrib.auth import login, password_validation
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.request import Request

from apps.accounts.repositories import UserRepository
from apps.accounts.services import setup_code

OWNER_ROLE: str = "admins"


class SetupDone(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "setup_done"
    default_detail = "Mesbah is already set up. Sign in instead."


class SetupCodeRejected(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "setup_code_rejected"
    default_detail = "That setup code doesn't match the one Mesbah printed."


class WeakOwnerPassword(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "weak_password"
    default_detail = "That password is too easy to guess."


class SetupService:
    def __init__(self) -> None:
        self.users: UserRepository = UserRepository()

    def needed(self) -> bool:
        if self.users.any_exists():
            return False
        setup_code.current_code()
        return True

    @transaction.atomic
    def complete(
        self, request: Request, *, code: str, username: str, password: str, **profile: Any
    ) -> User:
        if self.users.any_exists():
            raise SetupDone
        if not setup_code.matches(code):
            raise SetupCodeRejected
        try:
            password_validation.validate_password(password, User(username=username, **profile))
        except ValidationError as error:
            raise WeakOwnerPassword(detail=error.messages[0]) from error
        owner: User = self.users.create_owner(username=username, password=password, **profile)
        self.users.add_to_group(owner, OWNER_ROLE)
        if not setup_code.consume():
            raise SetupDone
        login(request, owner, backend="django.contrib.auth.backends.ModelBackend")
        return owner
