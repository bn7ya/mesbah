from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from asgiref.sync import async_to_sync, sync_to_async
from django.http import StreamingHttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.models.models import HubModel
from apps.serving.serializers import (
    OllamaChatSerializer,
    OllamaGenerateSerializer,
    OllamaShowSerializer,
)
from apps.serving.services.deployment_service import Target
from apps.serving.services.engine_client import EngineError
from apps.serving.services.errors import EngineFailed
from apps.serving.services.gateway_service import GatewayService, Served
from apps.serving.views.compat import CompatView, failure
from mesbah import __version__

NANOSECONDS: int = 1_000_000_000


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _engine_body(
    served: Served, messages: list[dict[str, Any]], data: dict[str, Any]
) -> dict[str, object]:
    generation: dict[str, Any] = served.project.generation
    options: dict[str, Any] = data.get("options") or {}
    think: object = data.get("think")
    limit: object = options.get("num_predict")
    return {
        "messages": messages,
        "temperature": options.get("temperature", generation.get("temperature")),
        "top_p": options.get("top_p", generation.get("top_p")),
        "max_tokens": limit
        if isinstance(limit, int) and limit > 0
        else generation.get("max_tokens"),
        "chat_template_kwargs": {
            "enable_thinking": GatewayService.thinking_default(served) if think is None else think
        },
    }


class OllamaView(CompatView):
    def body(self, code: str, message: str) -> dict[str, object]:
        return {"error": message}

    def answer(
        self,
        gateway: GatewayService,
        served: Served,
        body: dict[str, object],
        stream: bool,
        shape: str,
    ) -> Response | StreamingHttpResponse:
        lines: AsyncIterator[str] = self.lines(gateway, served, body, shape)
        if stream:
            response: StreamingHttpResponse = StreamingHttpResponse(
                lines, content_type="application/x-ndjson"
            )
            response["X-Accel-Buffering"] = "no"
            return response
        return Response(self.single(lines))

    def single(self, lines: AsyncIterator[str]) -> dict[str, Any]:
        async def gather() -> list[dict[str, Any]]:
            return [json.loads(line) async for line in lines]

        parts: list[dict[str, Any]] = async_to_sync(gather)()
        last: dict[str, Any] = parts[-1]
        if "error" in last:
            return last
        merged: dict[str, Any] = dict(last)
        for key in ("message", "response"):
            if key not in last:
                continue
            if key == "message":
                merged["message"] = {
                    "role": "assistant",
                    "content": "".join(part["message"]["content"] for part in parts),
                    "thinking": "".join(part["message"].get("thinking", "") for part in parts),
                }
            else:
                merged["response"] = "".join(part["response"] for part in parts)
                merged["thinking"] = "".join(part.get("thinking", "") for part in parts)
        return merged

    async def lines(
        self, gateway: GatewayService, served: Served, body: dict[str, object], shape: str
    ) -> AsyncIterator[str]:
        started: float = time.monotonic()

        def line(text: str, thinking: str, **extra: Any) -> str:
            data: dict[str, Any] = {"model": served.name, "created_at": _now()}
            if shape == "message":
                message: dict[str, str] = {"role": "assistant", "content": text}
                if thinking:
                    message["thinking"] = thinking
                data["message"] = message
            else:
                data["response"] = text
                if thinking:
                    data["thinking"] = thinking
            data.update(extra)
            return json.dumps(data, ensure_ascii=False) + "\n"

        prompt: int | None = None
        produced: int | None = None
        finish: str = "stop"
        try:
            target: Target = await sync_to_async(gateway.target)(served)
            async for piece in gateway.stream(target, body):
                if piece.kind == "content":
                    yield line(piece.text, "", done=False)
                elif piece.kind == "thinking":
                    yield line("", piece.text, done=False)
                elif piece.kind == "finish":
                    finish = piece.text
                else:
                    prompt, produced = piece.prompt_tokens, piece.completion_tokens
        except (EngineError, EngineFailed) as error:
            exc: Exception = (
                EngineFailed(error.code, error.detail) if isinstance(error, EngineError) else error
            )
            yield json.dumps({"error": failure(exc)[2]}) + "\n"
            return
        duration: int = int((time.monotonic() - started) * NANOSECONDS)
        yield line(
            "",
            "",
            done=True,
            done_reason=finish,
            total_duration=duration,
            prompt_eval_count=prompt or 0,
            eval_count=produced or 0,
        )


class OllamaChatView(OllamaView):
    @extend_schema(
        operation_id="ollama_chat",
        summary="Chat, as Ollama serves it",
        description="Newline-delimited JSON when `stream` is on (the default), like Ollama.",
        request=OllamaChatSerializer,
        responses={200: OpenApiResponse(OpenApiTypes.OBJECT)},
        tags=["ollama"],
    )
    def post(self, request: Request) -> Response | StreamingHttpResponse:
        payload: OllamaChatSerializer = OllamaChatSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data: dict[str, Any] = dict(payload.validated_data)
        gateway: GatewayService = GatewayService(request.user)
        served: Served = gateway.resolve(data["model"])
        body: dict[str, object] = _engine_body(served, data["messages"], data)
        return self.answer(gateway, served, body, data["stream"], "message")


class OllamaGenerateView(OllamaView):
    @extend_schema(
        operation_id="ollama_generate",
        summary="Generate from a prompt, as Ollama serves it",
        request=OllamaGenerateSerializer,
        responses={200: OpenApiResponse(OpenApiTypes.OBJECT)},
        tags=["ollama"],
    )
    def post(self, request: Request) -> Response | StreamingHttpResponse:
        payload: OllamaGenerateSerializer = OllamaGenerateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data: dict[str, Any] = dict(payload.validated_data)
        gateway: GatewayService = GatewayService(request.user)
        served: Served = gateway.resolve(data["model"])
        system: str = data.get("system") or served.project.system_prompt
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}] if system else []
        messages.append({"role": "user", "content": data["prompt"]})
        body: dict[str, object] = _engine_body(served, messages, data)
        return self.answer(gateway, served, body, data["stream"], "response")


def _details(served: Served) -> dict[str, Any]:
    base: HubModel | None = served.project.base_model
    parameters: int | None = None if base is None else base.parameters
    return {
        "parent_model": "" if base is None else base.repo_id,
        "format": "safetensors",
        "family": "" if base is None else base.model_type,
        "families": [] if base is None else [base.model_type],
        "parameter_size": "" if parameters is None else f"{parameters / 1e9:.1f}B",
        "quantization_level": "",
    }


class OllamaTagsView(OllamaView):
    @extend_schema(
        operation_id="ollama_tags",
        summary="Models, as Ollama lists them",
        responses={200: OpenApiResponse(OpenApiTypes.OBJECT)},
        tags=["ollama"],
    )
    def get(self, request: Request) -> Response:
        return Response(
            {
                "models": [
                    {
                        "name": entry.name,
                        "model": entry.name,
                        "modified_at": entry.version.updated_at.isoformat(),
                        "size": entry.version.size_bytes or entry.version.full_size_bytes,
                        "digest": entry.version.pk.hex,
                        "details": _details(entry),
                    }
                    for entry in GatewayService(request.user).served()
                ]
            }
        )


class OllamaShowView(OllamaView):
    @extend_schema(
        operation_id="ollama_show",
        summary="One model, as Ollama describes it",
        request=OllamaShowSerializer,
        responses={200: OpenApiResponse(OpenApiTypes.OBJECT)},
        tags=["ollama"],
    )
    def post(self, request: Request) -> Response:
        payload: OllamaShowSerializer = OllamaShowSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        served: Served = GatewayService(request.user).resolve(payload.validated_data["model"])
        capabilities: list[str] = ["completion"]
        if GatewayService.thinking_default(served):
            capabilities.append("thinking")
        return Response(
            {
                "modelfile": "",
                "parameters": "",
                "template": "",
                "system": served.project.system_prompt,
                "details": _details(served),
                "model_info": {},
                "capabilities": capabilities,
                "modified_at": served.version.updated_at.isoformat(),
            }
        )


class OllamaVersionView(OllamaView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="ollama_version",
        summary="The version Ollama clients ask for",
        responses={200: OpenApiResponse(OpenApiTypes.OBJECT)},
        tags=["ollama"],
    )
    def get(self, request: Request) -> Response:
        return Response({"version": __version__})
