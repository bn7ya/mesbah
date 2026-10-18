from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from asgiref.sync import async_to_sync, sync_to_async
from django.http import StreamingHttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response

from apps.serving.serializers import ChatCompletionSerializer
from apps.serving.services.deployment_service import Target
from apps.serving.services.engine_client import EngineError
from apps.serving.services.errors import EngineFailed
from apps.serving.services.gateway_service import Collected, GatewayService, Served
from apps.serving.views.compat import CompatView, failure


def engine_body(served: Served, request: dict[str, Any]) -> dict[str, object]:
    generation: dict[str, Any] = served.project.generation
    options: dict[str, Any] = request.get("chat_template_kwargs") or {}
    thinking: object = options.get("enable_thinking", GatewayService.thinking_default(served))
    limit: object = (
        request.get("max_completion_tokens")
        or request.get("max_tokens")
        or generation.get("max_tokens")
    )
    temperature: object = request.get("temperature")
    top_p: object = request.get("top_p")
    return {
        "messages": request["messages"],
        "temperature": generation.get("temperature") if temperature is None else temperature,
        "top_p": generation.get("top_p") if top_p is None else top_p,
        "max_tokens": limit,
        "chat_template_kwargs": {"enable_thinking": bool(thinking)},
    }


class ModelListView(CompatView):
    @extend_schema(
        operation_id="openai_models",
        summary="Models, as OpenAI lists them",
        description="Each project by its name (its active version) and each version as name:vN.",
        responses={200: OpenApiResponse(OpenApiTypes.OBJECT)},
        tags=["openai"],
    )
    def get(self, request: Request) -> Response:
        served: list[Served] = GatewayService(request.user).served()
        return Response(
            {
                "object": "list",
                "data": [
                    {
                        "id": entry.name,
                        "object": "model",
                        "created": int(entry.version.created_at.timestamp()),
                        "owned_by": "mesbah",
                    }
                    for entry in served
                ],
            }
        )


class ChatCompletionView(CompatView):
    @extend_schema(
        operation_id="openai_chat",
        summary="Chat completions, as OpenAI serves them",
        description=(
            "`model` is a project name (its active version), `name:vN` or `name:latest`. "
            "Thinking arrives as `reasoning_content`; `chat_template_kwargs.enable_thinking` "
            "turns it on or off."
        ),
        request=ChatCompletionSerializer,
        responses={200: OpenApiResponse(OpenApiTypes.OBJECT)},
        tags=["openai"],
    )
    def post(self, request: Request) -> Response | StreamingHttpResponse:
        payload: ChatCompletionSerializer = ChatCompletionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data: dict[str, Any] = dict(payload.validated_data)
        gateway: GatewayService = GatewayService(request.user)
        served: Served = gateway.resolve(data["model"])
        body: dict[str, object] = engine_body(served, data)
        reply: str = f"chatcmpl-{uuid.uuid4().hex}"
        if data["stream"]:
            usage: bool = bool((data.get("stream_options") or {}).get("include_usage"))
            response: StreamingHttpResponse = StreamingHttpResponse(
                self.chunks(gateway, served, body, reply, usage), content_type="text/event-stream"
            )
            response["Cache-Control"] = "no-cache"
            response["X-Accel-Buffering"] = "no"
            return response
        try:
            collected: Collected = async_to_sync(gateway.collect)(gateway.target(served), body)
        except EngineError as error:
            raise EngineFailed(error.code, error.detail) from error
        return Response(completion(reply, served.name, collected))

    async def chunks(
        self,
        gateway: GatewayService,
        served: Served,
        body: dict[str, object],
        reply: str,
        usage: bool,
    ) -> AsyncIterator[str]:
        created: int = int(time.time())

        def chunk(delta: dict[str, Any], finish: str | None = None) -> str:
            data: dict[str, Any] = {
                "id": reply,
                "object": "chat.completion.chunk",
                "created": created,
                "model": served.name,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        yield chunk({"role": "assistant", "content": ""})
        counts: dict[str, int | None] = {"prompt": None, "completion": None}
        finish: str = "stop"
        try:
            target: Target = await sync_to_async(gateway.target)(served)
            async for piece in gateway.stream(target, body):
                if piece.kind == "content":
                    yield chunk({"content": piece.text})
                elif piece.kind == "thinking":
                    yield chunk({"reasoning_content": piece.text})
                elif piece.kind == "finish":
                    finish = piece.text
                else:
                    counts = {"prompt": piece.prompt_tokens, "completion": piece.completion_tokens}
        except (EngineError, EngineFailed) as error:
            exc: Exception = (
                EngineFailed(error.code, error.detail) if isinstance(error, EngineError) else error
            )
            name: str = str(getattr(exc, "default_code", "engine_failed"))
            message: str = failure(exc)[2]
            yield f"data: {json.dumps(self.body(name, message), ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return
        yield chunk({}, finish)
        if usage:
            data: dict[str, Any] = {
                "id": reply,
                "object": "chat.completion.chunk",
                "created": created,
                "model": served.name,
                "choices": [],
                "usage": _usage(counts["prompt"], counts["completion"]),
            }
            yield f"data: {json.dumps(data)}\n\n"
        yield "data: [DONE]\n\n"


def completion(reply: str, model: str, collected: Collected) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": "".join(collected.content)}
    thinking: str = "".join(collected.thinking).strip()
    if thinking:
        message["reasoning_content"] = thinking
    return {
        "id": reply,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": collected.finish_reason}],
        "usage": _usage(collected.prompt_tokens, collected.completion_tokens),
    }


def _usage(prompt: int | None, completion_tokens: int | None) -> dict[str, int]:
    asked: int = prompt or 0
    answered: int = completion_tokens or 0
    return {"prompt_tokens": asked, "completion_tokens": answered, "total_tokens": asked + answered}
