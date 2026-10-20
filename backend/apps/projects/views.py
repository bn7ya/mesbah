from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.pages import PAGE_PARAMETERS, page_of, paginate
from apps.members.permissions import ViewersReadTrainersWrite
from apps.projects.models import Project
from apps.projects.serializers import (
    NewProjectSerializer,
    ProjectChangeSerializer,
    ProjectSerializer,
)
from apps.projects.services import ProjectService


class ProjectListView(APIView):
    permission_classes = [ViewersReadTrainersWrite]

    @extend_schema(
        operation_id="projects_list",
        summary="Projects",
        parameters=PAGE_PARAMETERS,
        responses={200: page_of(ProjectSerializer)},
    )
    def get(self, request: Request) -> Response:
        service: ProjectService = ProjectService(request.user)

        def render(projects: Iterable[Project]) -> list[Any]:
            return [ProjectSerializer(service.describe(project)).data for project in projects]

        return paginate(request, self, service.listing(), render)

    @extend_schema(
        summary="Start a project from a downloaded model",
        request=NewProjectSerializer,
        responses={201: ProjectSerializer},
    )
    def post(self, request: Request) -> Response:
        payload: NewProjectSerializer = NewProjectSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        fields: dict[str, Any] = dict(payload.validated_data)
        fields["base_model"] = str(fields["base_model"])
        created: dict[str, Any] = ProjectService(request.user).create(**fields)
        return Response(ProjectSerializer(created).data, status=status.HTTP_201_CREATED)


class ProjectDetailView(APIView):
    permission_classes = [ViewersReadTrainersWrite]

    @extend_schema(
        operation_id="projects_detail", summary="One project", responses={200: ProjectSerializer}
    )
    def get(self, request: Request, project_id: str) -> Response:
        service: ProjectService = ProjectService(request.user)
        return Response(ProjectSerializer(service.describe(service.find(project_id))).data)

    @extend_schema(
        summary="Change a project's name, prompt or reply settings",
        request=ProjectChangeSerializer,
        responses={200: ProjectSerializer},
    )
    def patch(self, request: Request, project_id: str) -> Response:
        payload: ProjectChangeSerializer = ProjectChangeSerializer(data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        changed: dict[str, Any] = ProjectService(request.user).change(
            project_id, **payload.validated_data
        )
        return Response(ProjectSerializer(changed).data)

    @extend_schema(summary="Remove a project", request=None, responses={204: None})
    def delete(self, request: Request, project_id: str) -> Response:
        ProjectService(request.user).remove(project_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
