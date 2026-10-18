from __future__ import annotations

from django.contrib.auth.models import AnonymousUser, User
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.members.roles import ADMINS, REVIEWERS, TRAINERS, VIEWERS, Role, at_least


class RoleAtLeast(BasePermission):
    role: Role = VIEWERS
    message: str = "You don't have access to this."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user: User | AnonymousUser = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return False
        if user.is_superuser:
            return True
        return user.groups.filter(name__in=at_least(self.role)).exists()


class IsViewer(RoleAtLeast):
    role = VIEWERS


class IsReviewer(RoleAtLeast):
    role = REVIEWERS


class IsTrainer(RoleAtLeast):
    role = TRAINERS


class IsAdministrator(RoleAtLeast):
    role = ADMINS


class ViewersReadTrainersWrite(BasePermission):
    message: str = "You don't have access to this."

    def has_permission(self, request: Request, view: APIView) -> bool:
        needed: RoleAtLeast = IsViewer() if request.method in SAFE_METHODS else IsTrainer()
        return needed.has_permission(request, view)


class ViewersReadAdminsWrite(BasePermission):
    message: str = "You don't have access to this."

    def has_permission(self, request: Request, view: APIView) -> bool:
        needed: RoleAtLeast = IsViewer() if request.method in SAFE_METHODS else IsAdministrator()
        return needed.has_permission(request, view)
