from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from django.http import FileResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.pages import PAGE_PARAMETERS, page_of, paginate
from apps.members.permissions import IsTrainer, IsViewer, ViewersReadTrainersWrite
from apps.versions.models import Export, ModelVersion
from apps.versions.serializers import (
    ChangesSerializer,
    ExportSerializer,
    NewExportSerializer,
    VersionChangeSerializer,
    VersionListQuerySerializer,
    VersionSerializer,
)
from apps.versions.services import Download, ExportService, VersionService


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


class ExportListView(APIView):
    permission_classes = [ViewersReadTrainersWrite]

    @extend_schema(
        operation_id="versions_exports",
        summary="A version's exports, newest first",
        parameters=PAGE_PARAMETERS,
        responses={200: page_of(ExportSerializer)},
    )
    def get(self, request: Request, version_id: str) -> Response:
        service: ExportService = ExportService(request.user)

        def render(exports: Iterable[Export]) -> list[Any]:
            return [ExportSerializer(service.describe(export)).data for export in exports]

        return paginate(request, self, service.listing(version_id), render)

    @extend_schema(
        summary="Export a version",
        description=(
            "`lora`: the adapter as a zip, for vLLM and PEFT. `merged`: full weights with the "
            "change folded in, for any engine. `gguf`: one file for llama.cpp and Ollama, with "
            "a Modelfile; `out_type` picks f16, bf16 or q8_0."
        ),
        request=NewExportSerializer,
        responses={202: ExportSerializer},
    )
    def post(self, request: Request, version_id: str) -> Response:
        payload: NewExportSerializer = NewExportSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        service: ExportService = ExportService(request.user)
        export: Export = service.create(version_id, **payload.validated_data)
        return Response(
            ExportSerializer(service.describe(export)).data, status=status.HTTP_202_ACCEPTED
        )


class ExportDetailView(APIView):
    permission_classes = [ViewersReadTrainersWrite]

    @extend_schema(
        operation_id="versions_export", summary="One export", responses={200: ExportSerializer}
    )
    def get(self, request: Request, export_id: str) -> Response:
        service: ExportService = ExportService(request.user)
        return Response(ExportSerializer(service.describe(service.find(export_id))).data)

    @extend_schema(summary="Remove an export and its files", request=None, responses={204: None})
    def delete(self, request: Request, export_id: str) -> Response:
        ExportService(request.user).remove(export_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExportDownloadView(APIView):
    permission_classes = [IsViewer]

    @extend_schema(
        operation_id="versions_export_download",
        summary="Download an export",
        responses={(200, "application/octet-stream"): OpenApiResponse(OpenApiTypes.BINARY)},
    )
    def get(self, request: Request, export_id: str) -> FileResponse:
        download: Download = ExportService(request.user).download(export_id)
        return FileResponse(
            download.path.open("rb"), as_attachment=True, filename=download.filename
        )


class ChangesView(APIView):
    permission_classes = [IsViewer]

    @extend_schema(
        operation_id="versions_changes",
        summary="How much each layer and module changed",
        description="The size of the change (its norm) per layer and module, from training.",
        responses={200: ChangesSerializer},
    )
    def get(self, request: Request, version_id: str) -> Response:
        return Response(ChangesSerializer(VersionService(request.user).changes(version_id)).data)
