from __future__ import annotations

from django.contrib.auth.models import AnonymousUser, User
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class InGroup(BasePermission):
    group: str = ""
    message: str = "You don't have access to this."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user: User | AnonymousUser = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if not self.group:
            raise NotImplementedError(f"{type(self).__name__} must set `group`.")
        return user.groups.filter(name=self.group).exists()


class IsOwnerOrStaff(BasePermission):
    message: str = "You don't have access to this."

    def has_object_permission(self, request: Request, view: APIView, obj: object) -> bool:
        user: User | AnonymousUser = request.user
        if not user or not user.is_authenticated:
            return False
        return user.is_staff or getattr(obj, "created_by_id", None) == user.pk
