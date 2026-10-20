from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.system.permissions import CanManageSystem
from apps.system.serializers import (
    GpuSelectionSerializer,
    HuggingFaceTokenSerializer,
    SystemOverviewSerializer,
)
from apps.system.services import SystemService


class SystemView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="This machine",
        description=(
            "GPUs, RAM, storage, the installed optional parts and whether a HuggingFace "
            "token is saved. The token itself is never returned."
        ),
        responses={200: SystemOverviewSerializer},
    )
    def get(self, request: Request) -> Response:
        overview: dict[str, Any] = SystemService(request.user).overview()
        return Response(SystemOverviewSerializer(overview).data)


class GpuSelectionView(APIView):
    permission_classes = [CanManageSystem]

    @extend_schema(
        summary="Choose the GPUs Mesbah uses",
        description="An empty list goes back to the automatic choice: the largest GPU.",
        request=GpuSelectionSerializer,
        responses={200: SystemOverviewSerializer},
    )
    def put(self, request: Request) -> Response:
        payload: GpuSelectionSerializer = GpuSelectionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        overview: dict[str, Any] = SystemService(request.user).select_gpus(
            payload.validated_data["gpus"]
        )
        return Response(SystemOverviewSerializer(overview).data)


class HuggingFaceTokenView(APIView):
    permission_classes = [CanManageSystem]

    @extend_schema(
        summary="Save the HuggingFace token",
        description="Checked with HuggingFace before it is saved, then stored encrypted.",
        request=HuggingFaceTokenSerializer,
        responses={200: SystemOverviewSerializer},
    )
    def put(self, request: Request) -> Response:
        payload: HuggingFaceTokenSerializer = HuggingFaceTokenSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        overview: dict[str, Any] = SystemService(request.user).save_huggingface_token(
            payload.validated_data["token"]
        )
        return Response(SystemOverviewSerializer(overview).data)

    @extend_schema(
        summary="Remove the HuggingFace token",
        request=None,
        responses={200: SystemOverviewSerializer},
    )
    def delete(self, request: Request) -> Response:
        overview: dict[str, Any] = SystemService(request.user).remove_huggingface_token()
        return Response(SystemOverviewSerializer(overview).data)
