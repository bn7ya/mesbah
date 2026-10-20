from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission, User

UserModel: type[User] = get_user_model()


class UserRepository:
    def find_by_username(self, username: str) -> User | None:
        return UserModel.objects.filter(username__iexact=username).first()

    def find_by_email(self, email: str) -> User | None:
        return UserModel.objects.filter(email__iexact=email).first()

    def with_groups(self, user_id: int) -> User | None:
        return (
            UserModel.objects.filter(pk=user_id)
            .prefetch_related("groups", "groups__permissions", "user_permissions")
            .first()
        )

    def group_names(self, user: User) -> list[str]:
        return sorted(user.groups.values_list("name", flat=True))

    def permission_codenames(self, user: User) -> list[str]:
        return sorted(user.get_all_permissions())

    def in_group(self, user: User, name: str) -> bool:
        return user.groups.filter(name=name).exists()

    def ensure_group(self, name: str) -> Group:
        group, _ = Group.objects.get_or_create(name=name)
        return group

    def any_exists(self) -> bool:
        return UserModel.objects.exists()

    def create_owner(self, *, username: str, password: str, **fields: Any) -> User:
        return UserModel.objects.create_superuser(username=username, password=password, **fields)

    def create(self, *, username: str, password: str, **fields: Any) -> User:
        return UserModel.objects.create_user(username=username, password=password, **fields)

    def add_to_group(self, user: User, name: str) -> User:
        user.groups.add(self.ensure_group(name))
        return user

    def grant_to_group(self, group: Group, codename: str) -> Group:
        group.permissions.add(Permission.objects.get(codename=codename))
        return group

    def deactivate(self, user: User) -> User:
        user.is_active = False
        user.save(update_fields=["is_active"])
        return user
