from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.pages import PAGE_PARAMETERS, page_of, paginate
from apps.members.permissions import IsTrainer, ViewersReadAdminsWrite
from apps.serving.models import Engine
from apps.serving.serializers import (
    EngineChangeSerializer,
    EngineSerializer,
    NewEngineSerializer,
)
from apps.serving.services import EngineService


class EngineListView(APIView):
    permission_classes = [ViewersReadAdminsWrite]

    @extend_schema(
        operation_id="serving_engines",
        summary="Engines and what each has loaded",
        description="Each engine is asked what it holds, so a stopped one shows as not running.",
        parameters=PAGE_PARAMETERS,
        responses={200: page_of(EngineSerializer)},
    )
    def get(self, request: Request) -> Response:
        service: EngineService = EngineService(request.user)

        def render(engines: Iterable[Engine]) -> list[Any]:
            return [EngineSerializer(service.describe(engine)).data for engine in engines]

        return paginate(request, self, service.listing(), render)

    @extend_schema(
        summary="Connect an engine",
        description=(
            "vLLM and Ollama get versions loaded onto them (vLLM must read the version's folder; "
            "Ollama needs a GGUF export). llama.cpp and any OpenAI-compatible server answer "
            "with the one model they serve, named in `model_name`."
        ),
        request=NewEngineSerializer,
        responses={201: EngineSerializer},
    )
    def post(self, request: Request) -> Response:
        payload: NewEngineSerializer = NewEngineSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        service: EngineService = EngineService(request.user)
        engine: Engine = service.create(**payload.validated_data)
        return Response(
            EngineSerializer(service.describe(engine)).data, status=status.HTTP_201_CREATED
        )


class EngineDetailView(APIView):
    permission_classes = [ViewersReadAdminsWrite]

    @extend_schema(
        operation_id="serving_engine", summary="One engine", responses={200: EngineSerializer}
    )
    def get(self, request: Request, engine_id: str) -> Response:
        service: EngineService = EngineService(request.user)
        return Response(EngineSerializer(service.describe(service.find(engine_id))).data)

    @extend_schema(
        summary="Change an engine",
        description=(
            "An empty `api_key` removes it. The built-in engine takes a name, on/off and "
            "default only."
        ),
        request=EngineChangeSerializer,
        responses={200: EngineSerializer},
    )
    def patch(self, request: Request, engine_id: str) -> Response:
        payload: EngineChangeSerializer = EngineChangeSerializer(data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        service: EngineService = EngineService(request.user)
        engine: Engine = service.change(engine_id, **payload.validated_data)
        return Response(EngineSerializer(service.describe(engine)).data)

    @extend_schema(summary="Disconnect an engine", request=None, responses={204: None})
    def delete(self, request: Request, engine_id: str) -> Response:
        EngineService(request.user).remove(engine_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class UnloadEngineView(APIView):
    permission_classes = [IsTrainer]

    @extend_schema(
        summary="Free the engine's memory",
        description="The next chat loads the model again, which takes a while.",
        request=None,
        responses={200: EngineSerializer},
    )
    def post(self, request: Request, engine_id: str) -> Response:
        return Response(EngineSerializer(EngineService(request.user).unload(engine_id)).data)
