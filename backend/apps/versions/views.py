from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.pages import PAGE_PARAMETERS, page_of, paginate
from apps.members.permissions import IsTrainer, IsViewer, ViewersReadTrainersWrite
from apps.versions.models import ModelVersion
from apps.versions.serializers import (
    VersionChangeSerializer,
    VersionListQuerySerializer,
    VersionSerializer,
)
from apps.versions.services import VersionService


class VersionListView(APIView):
    permission_classes = [IsViewer]

    @extend_schema(
        operation_id="versions_tree",
        summary="A project's versions, oldest first",
        description="Each version names its parent, so the list draws as a tree.",
        parameters=[
            OpenApiParameter("project", str, required=True, description="The project's id."),
            *PAGE_PARAMETERS,
        ],
        responses={200: page_of(VersionSerializer)},
    )
    def get(self, request: Request) -> Response:
        query: VersionListQuerySerializer = VersionListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        project_id: str = str(query.validated_data["project"])
        service: VersionService = VersionService(request.user)
        active: object = service.project(project_id).active_version_id

        def render(versions: Iterable[ModelVersion]) -> list[Any]:
            return [
                VersionSerializer(service.describe(version, active)).data for version in versions
            ]

        return paginate(request, self, service.tree(project_id), render)


class VersionView(APIView):
    permission_classes = [ViewersReadTrainersWrite]

    @extend_schema(
        operation_id="versions_detail", summary="One version", responses={200: VersionSerializer}
    )
    def get(self, request: Request, version_id: str) -> Response:
        service: VersionService = VersionService(request.user)
        return Response(VersionSerializer(service.describe(service.find(version_id))).data)

    @extend_schema(
        summary="Rename a version or change its notes",
        request=VersionChangeSerializer,
        responses={200: VersionSerializer},
    )
    def patch(self, request: Request, version_id: str) -> Response:
        payload: VersionChangeSerializer = VersionChangeSerializer(data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        changed: dict[str, Any] = VersionService(request.user).change(
            version_id, **payload.validated_data
        )
        return Response(VersionSerializer(changed).data)

    @extend_schema(
        summary="Remove a version",
        description="Its children move up to its parent. The base and the active version stay.",
        request=None,
        responses={204: None},
    )
    def delete(self, request: Request, version_id: str) -> Response:
        VersionService(request.user).remove(version_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ActivateVersionView(APIView):
    permission_classes = [IsTrainer]

    @extend_schema(
        summary="Make this the version everyone chats with",
        description="Rolling back is activating an older version.",
        request=None,
        responses={200: VersionSerializer},
    )
    def post(self, request: Request, version_id: str) -> Response:
        return Response(VersionSerializer(VersionService(request.user).activate(version_id)).data)
