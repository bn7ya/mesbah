from __future__ import annotations

import json
import secrets
import threading
import time
import uuid
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field

import anyio
from starlette.applications import Starlette
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool
from starlette.datastructures import Headers
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from mesbah import parts
from mesbah.runtime.engine import Engine, Generation
from mesbah.runtime.errors import EngineError, InvalidRequest
from mesbah.runtime.specs import ChatRequest, LoadSpec
from mesbah.think import Piece, ThinkingStream, split_thinking

PUBLIC_PATHS: frozenset[str] = frozenset({"/health"})
OWNER: str = "mesbah"
DONE: str = "data: [DONE]\n\n"
STREAM_HEADERS: dict[str, str] = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def error_body(status: int, code: str, message: str) -> dict[str, object]:
    kind: str = "invalid_request_error" if status < 500 else "server_error"
    return {"error": {"message": message, "type": kind, "code": code}}


def error_response(
    status: int, code: str, message: str, headers: Mapping[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(error_body(status, code, message), status_code=status, headers=headers)


def sse(body: Mapping[str, object]) -> str:
    return f"data: {json.dumps(body, ensure_ascii=False)}\n\n"


def deltas(pieces: list[Piece]) -> list[dict[str, str]]:
    return [
        {"reasoning_content" if kind == "thinking" else "content": text} for kind, text in pieces
    ]


def installed_parts() -> list[dict[str, str | None]]:
    return [{"name": part.name, "version": part.version} for part in parts.parts()]


def usage(generation: Generation) -> dict[str, int]:
    return {
        "prompt_tokens": generation.prompt_tokens,
        "completion_tokens": generation.completion_tokens,
        "total_tokens": generation.prompt_tokens + generation.completion_tokens,
    }


async def read_json(request: Request) -> object:
    try:
        body: object = await request.json()
    except ValueError as error:
        raise InvalidRequest("The body must be JSON.") from error
    return body


async def finish(generation: Generation) -> None:
    with anyio.CancelScope(shield=True):
        await run_in_threadpool(generation.close)


async def on_error(_request: Request, error: Exception) -> Response:
    failure: EngineError = error if isinstance(error, EngineError) else EngineError(str(error))
    return error_response(failure.status, failure.code, failure.message)


@dataclass(frozen=True)
class Reply:
    model: str
    ident: str = field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex}")
    created: int = field(default_factory=lambda: int(time.time()))

    def chunk(
        self,
        delta: Mapping[str, str],
        finish_reason: str | None = None,
        tokens: Mapping[str, int] | None = None,
    ) -> str:
        body: dict[str, object] = {
            "id": self.ident,
            "object": "chat.completion.chunk",
            "created": self.created,
            "model": self.model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }
        if tokens is not None:
            body["usage"] = tokens
        return sse(body)

    def completion(self, generation: Generation, thinking: str, answer: str) -> dict[str, object]:
        return {
            "id": self.ident,
            "object": "chat.completion",
            "created": self.created,
            "model": self.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": answer,
                        "reasoning_content": thinking or None,
                    },
                    "finish_reason": generation.finish_reason,
                }
            ],
            "usage": usage(generation),
        }


class RequireToken:
    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app: ASGIApp = app
        self.expected: bytes = f"Bearer {token}".encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] not in PUBLIC_PATHS:
            supplied: str = Headers(scope=scope).get("authorization", "")
            if not secrets.compare_digest(supplied.encode(), self.expected):
                refusal: JSONResponse = error_response(
                    401,
                    "invalid_api_key",
                    "A valid bearer token is required.",
                    {"WWW-Authenticate": "Bearer"},
                )
                await refusal(scope, receive, send)
                return
        await self.app(scope, receive, send)


class Api:
    def __init__(self, engine: Engine) -> None:
        self.engine: Engine = engine

    async def health(self, _request: Request) -> Response:
        return JSONResponse({"status": "ok"})

    async def models(self, _request: Request) -> Response:
        created: int = int(time.time())
        cards: list[dict[str, object]] = [
            {"id": name, "object": "model", "created": created, "owned_by": OWNER}
            for name in self.engine.models()
        ]
        return JSONResponse({"object": "list", "data": cards})

    async def status(self, _request: Request) -> Response:
        return JSONResponse({**self.engine.status(), "parts": installed_parts()})

    async def load(self, request: Request) -> Response:
        spec: LoadSpec = LoadSpec.from_json(await read_json(request))
        await run_in_threadpool(self.engine.load, spec)
        return JSONResponse(self.engine.status())

    async def unload(self, _request: Request) -> Response:
        await run_in_threadpool(self.engine.unload)
        return JSONResponse(self.engine.status())

    async def completions(self, request: Request) -> Response:
        chat: ChatRequest = ChatRequest.from_json(await read_json(request))
        stop: threading.Event = threading.Event()
        generation: Generation = self.engine.generate(chat, stop)
        reply: Reply = Reply(model=chat.model)
        if chat.stream:
            return StreamingResponse(
                self.events(generation, reply),
                media_type="text/event-stream",
                headers=STREAM_HEADERS,
            )
        pieces: list[str] = []
        try:
            async for piece in iterate_in_threadpool(generation):
                pieces.append(piece)
                if await request.is_disconnected():
                    stop.set()
        finally:
            await finish(generation)
        thinking, answer = split_thinking("".join(pieces), starts_inside=generation.opens_thinking)
        return JSONResponse(reply.completion(generation, thinking, answer))

    async def events(self, generation: Generation, reply: Reply) -> AsyncIterator[str]:
        try:
            yield reply.chunk({"role": "assistant", "content": ""})
            await run_in_threadpool(generation.begin)
            splitter: ThinkingStream = ThinkingStream(starts_inside=generation.opens_thinking)
            async for piece in iterate_in_threadpool(generation):
                for delta in deltas(splitter.feed(piece)):
                    yield reply.chunk(delta)
            for delta in deltas(splitter.close()):
                yield reply.chunk(delta)
            yield reply.chunk({}, generation.finish_reason, usage(generation))
        except EngineError as error:
            yield sse(error_body(error.status, error.code, error.message))
        finally:
            await finish(generation)
        yield DONE


def create_app(engine: Engine, token: str | None) -> Starlette:
    api: Api = Api(engine)
    routes: list[Route] = [
        Route("/health", api.health, methods=["GET"]),
        Route("/v1/models", api.models, methods=["GET"]),
        Route("/v1/chat/completions", api.completions, methods=["POST"]),
        Route("/admin/load", api.load, methods=["POST"]),
        Route("/admin/unload", api.unload, methods=["POST"]),
        Route("/admin/status", api.status, methods=["GET"]),
    ]
    middleware: list[Middleware] = [Middleware(RequireToken, token=token)] if token else []
    return Starlette(
        routes=routes,
        middleware=middleware,
        exception_handlers={EngineError: on_error, Exception: on_error},
    )
