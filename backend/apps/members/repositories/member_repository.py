from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, User
from django.db.models import Q, QuerySet

from apps.members.roles import LADDER, Role

UserModel: type[User] = get_user_model()


class MemberRepository:
    def listing(self) -> QuerySet[User]:
        return UserModel.objects.prefetch_related("groups").order_by("username")

    def find(self, user_id: int) -> User | None:
        return UserModel.objects.prefetch_related("groups").filter(pk=user_id).first()

    def username_taken(self, username: str) -> bool:
        return UserModel.objects.filter(username__iexact=username).exists()

    def create(self, *, username: str, password: str, **fields: Any) -> User:
        return UserModel.objects.create_user(username=username, password=password, **fields)

    def set_role(self, user: User, role: Role) -> User:
        user.groups.remove(*Group.objects.filter(name__in=LADDER))
        group, _ = Group.objects.get_or_create(name=role)
        user.groups.add(group)
        return user

    def update(self, user: User, **fields: Any) -> User:
        for name, value in fields.items():
            setattr(user, name, value)
        user.save(update_fields=list(fields))
        return user

    def active_count(self, role: Role) -> int:
        return (
            UserModel.objects.filter(is_active=True)
            .filter(Q(is_superuser=True) | Q(groups__name=role))
            .distinct()
            .count()
        )
