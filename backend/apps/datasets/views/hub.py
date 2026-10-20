from __future__ import annotations

from typing import Any

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.pages import page_of
from apps.datasets.serializers import (
    DatasetInspectionSerializer,
    HubDatasetSerializer,
    HubQuerySerializer,
    InspectQuerySerializer,
)
from apps.datasets.services import DatasetService
from apps.members.permissions import IsViewer


class HubSearchView(APIView):
    permission_classes = [IsViewer]

    @extend_schema(
        operation_id="datasets_hub_search",
        summary="Search HuggingFace datasets",
        description="An empty search lists popular datasets for text generation.",
        parameters=[OpenApiParameter("search", str)],
        responses={200: page_of(HubDatasetSerializer)},
    )
    def get(self, request: Request) -> Response:
        query: HubQuerySerializer = HubQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        service: DatasetService = DatasetService(request.user)
        search: str = query.validated_data["search"]
        found: list[dict[str, Any]] = service.search(search) if search else service.featured()
        rows: list[Any] = [HubDatasetSerializer(result).data for result in found]
        return Response({"count": len(rows), "next": None, "previous": None, "results": rows})


class HubInspectView(APIView):
    permission_classes = [IsViewer]

    @extend_schema(
        operation_id="datasets_hub_inspect",
        summary="What a HuggingFace dataset holds, and how its rows would be read",
        description=(
            "Lists the subsets and splits, the columns and the first rows. Pass `prompt` and "
            "`reply` (and optionally `thinking`) to read the rows with those columns instead "
            "of the detected layout."
        ),
        parameters=[
            OpenApiParameter("repo", str, required=True),
            OpenApiParameter("config", str),
            OpenApiParameter("split", str),
            OpenApiParameter("prompt", str),
            OpenApiParameter("reply", str),
            OpenApiParameter("thinking", str),
        ],
        responses={200: DatasetInspectionSerializer},
    )
    def get(self, request: Request) -> Response:
        query: InspectQuerySerializer = InspectQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        given: dict[str, Any] = query.validated_data
        columns: tuple[str, str, str] | None = (
            (given["prompt"], given["reply"], given["thinking"]) if given["prompt"] else None
        )
        inspected: dict[str, Any] = DatasetService(request.user).inspect(
            given["repo"], given["config"], given["split"], columns
        )
        return Response(DatasetInspectionSerializer(inspected).data)
