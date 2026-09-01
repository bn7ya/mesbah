"""The only place this app touches the ORM.

`User` comes from `django.contrib.auth`, so it does not inherit `BaseModel`
and has no `deleted_at` — deactivation is what "deleting" a user means here.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission, User

UserModel = get_user_model()


class UserRepository:
    """Reads and writes for users, groups and permissions."""

    def find_by_username(self, username: str) -> User | None:
        return UserModel.objects.filter(username__iexact=username).first()

    def find_by_email(self, email: str) -> User | None:
        return UserModel.objects.filter(email__iexact=email).first()

    def with_groups(self, user_id) -> User | None:
        """One user with groups and permissions prefetched."""
        return (
            UserModel.objects.filter(pk=user_id)
            .prefetch_related("groups", "groups__permissions", "user_permissions")
            .first()
        )

    def group_names(self, user: User) -> list[str]:
        return sorted(user.groups.values_list("name", flat=True))

    def permission_codenames(self, user: User) -> list[str]:
        """Every permission the user has, `app_label.codename`, sorted."""
        return sorted(user.get_all_permissions())

    def in_group(self, user: User, name: str) -> bool:
        return user.groups.filter(name=name).exists()

    def ensure_group(self, name: str) -> Group:
        group, _ = Group.objects.get_or_create(name=name)
        return group

    def create(self, *, username: str, password: str, **fields) -> User:
        """Create a user with a hashed password (never stored in plain text)."""
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
