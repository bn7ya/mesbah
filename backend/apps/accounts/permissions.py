"""Reusable permission classes.

Django Groups and Permissions are the only authorization system on the
Django side — these are thin adapters onto that, not a second one.
"""
from __future__ import annotations

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class InGroup(BasePermission):
    """Grants access to members of a named group.

    Subclass with the group name rather than instantiating::

        class IsOperator(InGroup):
            group = "operators"
    """

    group: str = ""
    message = "You don't have access to this."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if not self.group:
            raise NotImplementedError(f"{type(self).__name__} must set `group`.")
        return user.groups.filter(name=self.group).exists()


class IsOwnerOrStaff(BasePermission):
    """Object-level: the row's creator, or a staff member.

    Only useful on models inheriting `BaseModel` (every model in `apps/*`).
    """

    message = "You don't have access to this."

    def has_object_permission(self, request: Request, view: APIView, obj) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.is_staff or getattr(obj, "created_by_id", None) == user.pk
