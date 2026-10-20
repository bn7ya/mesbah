from __future__ import annotations

from typing import Any

from django.contrib.auth import password_validation
from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import QuerySet
from rest_framework.exceptions import NotFound

from apps.members.repositories import MemberRepository
from apps.members.roles import ADMINS, Role, highest
from apps.members.services.errors import (
    LastAdministrator,
    OwnerLocked,
    SelfDeactivation,
    UsernameTaken,
    WeakPassword,
)


class MemberService:
    def __init__(self, user: User | AnonymousUser) -> None:
        self.user: User | AnonymousUser = user
        self.members: MemberRepository = MemberRepository()

    def listing(self) -> QuerySet[User]:
        return self.members.listing()

    def describe(self, member: User) -> dict[str, Any]:
        groups: list[str] = [group.name for group in member.groups.all()]
        return {
            "id": member.pk,
            "username": member.username,
            "first_name": member.first_name,
            "last_name": member.last_name,
            "email": member.email,
            "role": highest(groups, superuser=member.is_superuser),
            "owner": member.is_superuser,
            "is_active": member.is_active,
            "is_self": member.pk == self.user.pk,
            "last_login": member.last_login,
            "date_joined": member.date_joined,
        }

    @transaction.atomic
    def add(self, *, username: str, password: str, role: Role, **profile: str) -> dict[str, Any]:
        if self.members.username_taken(username):
            raise UsernameTaken
        try:
            password_validation.validate_password(password, User(username=username, **profile))
        except ValidationError as error:
            raise WeakPassword(detail=error.messages[0]) from error
        member: User = self.members.create(username=username, password=password, **profile)
        self.members.set_role(member, role)
        return self.describe(member)

    @transaction.atomic
    def change(
        self, member_id: int, *, role: Role | None = None, is_active: bool | None = None
    ) -> dict[str, Any]:
        member: User | None = self.members.find(member_id)
        if member is None:
            raise NotFound
        if member.is_superuser and (role not in {None, ADMINS} or is_active is False):
            raise OwnerLocked
        if is_active is False and member.pk == self.user.pk:
            raise SelfDeactivation
        if self._removes_an_administrator(member, role, is_active):
            raise LastAdministrator
        if role is not None:
            self.members.set_role(member, role)
        if is_active is not None:
            self.members.update(member, is_active=is_active)
        refreshed: User | None = self.members.find(member_id)
        return self.describe(refreshed or member)

    def _removes_an_administrator(
        self, member: User, role: Role | None, is_active: bool | None
    ) -> bool:
        current: Role | None = highest(
            [group.name for group in member.groups.all()], superuser=member.is_superuser
        )
        if current != ADMINS or not member.is_active:
            return False
        leaves: bool = (role is not None and role != ADMINS) or is_active is False
        return leaves and self.members.active_count(ADMINS) <= 1
