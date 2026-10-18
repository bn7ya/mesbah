from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.pages import PAGE_PARAMETERS, page_of, paginate
from apps.members.permissions import IsTrainer
from apps.serving.models import ApiKey
from apps.serving.serializers import (
    ApiKeySerializer,
    CreatedApiKeySerializer,
    NewApiKeySerializer,
)
from apps.serving.services.api_key_service import ApiKeyService


class ApiKeyListView(APIView):
    permission_classes = [IsTrainer]

    @extend_schema(
        operation_id="serving_keys",
        summary="API keys",
        description="Administrators see every key; others see their own.",
        parameters=PAGE_PARAMETERS,
        responses={200: page_of(ApiKeySerializer)},
    )
    def get(self, request: Request) -> Response:
        service: ApiKeyService = ApiKeyService(request.user)

        def render(keys: Iterable[ApiKey]) -> list[Any]:
            return [ApiKeySerializer(service.describe(key)).data for key in keys]

        return paginate(request, self, service.listing(), render)

    @extend_schema(
        summary="Make an API key",
        description="The key is in this answer only; Mesbah keeps its digest.",
        request=NewApiKeySerializer,
        responses={201: CreatedApiKeySerializer},
    )
    def post(self, request: Request) -> Response:
        payload: NewApiKeySerializer = NewApiKeySerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        created: dict[str, Any] = ApiKeyService(request.user).create(payload.validated_data["name"])
        return Response(CreatedApiKeySerializer(created).data, status=status.HTTP_201_CREATED)


class ApiKeyDetailView(APIView):
    permission_classes = [IsTrainer]

    @extend_schema(summary="Revoke an API key", request=None, responses={204: None})
    def delete(self, request: Request, key_id: str) -> Response:
        ApiKeyService(request.user).revoke(key_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
