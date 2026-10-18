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
from apps.models.models import HubModel
from apps.models.serializers import (
    AddModelSerializer,
    HubQuerySerializer,
    HubResultSerializer,
    InspectionSerializer,
    InspectQuerySerializer,
    LibraryModelSerializer,
)
from apps.models.services import ModelService


class LibraryView(APIView):
    permission_classes = [ViewersReadTrainersWrite]

    @extend_schema(
        operation_id="models_library",
        summary="The model library",
        parameters=PAGE_PARAMETERS,
        responses={200: page_of(LibraryModelSerializer)},
    )
    def get(self, request: Request) -> Response:
        service: ModelService = ModelService(request.user)
        vram: int = service.system.usable_vram_bytes()

        def render(rows: Iterable[HubModel]) -> list[Any]:
            return [LibraryModelSerializer(service.describe(row, vram)).data for row in rows]

        return paginate(request, self, service.library(), render)

    @extend_schema(
        summary="Add a model from HuggingFace and start downloading it",
        request=AddModelSerializer,
        responses={202: LibraryModelSerializer},
    )
    def post(self, request: Request) -> Response:
        payload: AddModelSerializer = AddModelSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        added: dict[str, Any] = ModelService(request.user).add(payload.validated_data["repo_id"])
        return Response(LibraryModelSerializer(added).data, status=status.HTTP_202_ACCEPTED)


class LibraryModelView(APIView):
    permission_classes = [ViewersReadTrainersWrite]

    @extend_schema(
        operation_id="models_detail",
        summary="One model in the library",
        responses={200: LibraryModelSerializer},
    )
    def get(self, request: Request, model_id: str) -> Response:
        service: ModelService = ModelService(request.user)
        return Response(LibraryModelSerializer(service.describe(service.find(model_id))).data)

    @extend_schema(
        summary="Remove a model and its downloaded files", request=None, responses={204: None}
    )
    def delete(self, request: Request, model_id: str) -> Response:
        ModelService(request.user).remove(model_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CancelDownloadView(APIView):
    permission_classes = [IsTrainer]

    @extend_schema(summary="Stop a download", request=None, responses={200: LibraryModelSerializer})
    def post(self, request: Request, model_id: str) -> Response:
        return Response(LibraryModelSerializer(ModelService(request.user).cancel(model_id)).data)


class RetryDownloadView(APIView):
    permission_classes = [IsTrainer]

    @extend_schema(
        summary="Download a failed or stopped model again",
        request=None,
        responses={202: LibraryModelSerializer},
    )
    def post(self, request: Request, model_id: str) -> Response:
        retried: dict[str, Any] = ModelService(request.user).retry(model_id)
        return Response(LibraryModelSerializer(retried).data, status=status.HTTP_202_ACCEPTED)


class HubSearchView(APIView):
    permission_classes = [IsViewer]

    @extend_schema(
        summary="Search HuggingFace",
        description="An empty search lists popular text-generation models.",
        parameters=[
            OpenApiParameter("search", str),
            OpenApiParameter("task", str, enum=["text-generation", "text2text-generation"]),
        ],
        responses={200: page_of(HubResultSerializer)},
    )
    def get(self, request: Request) -> Response:
        query: HubQuerySerializer = HubQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        service: ModelService = ModelService(request.user)
        search: str = query.validated_data["search"]
        found: list[dict[str, Any]] = (
            service.search(search, query.validated_data["task"]) if search else service.featured()
        )
        rows: list[Any] = [HubResultSerializer(result).data for result in found]
        return Response({"count": len(rows), "next": None, "previous": None, "results": rows})


class HubInspectView(APIView):
    permission_classes = [IsViewer]

    @extend_schema(
        summary="What a HuggingFace model is, and whether it fits this machine",
        parameters=[OpenApiParameter("repo", str, required=True)],
        responses={200: InspectionSerializer},
    )
    def get(self, request: Request) -> Response:
        query: InspectQuerySerializer = InspectQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        inspected: dict[str, Any] = ModelService(request.user).inspect(query.validated_data["repo"])
        return Response(InspectionSerializer(inspected).data)
