from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal, cast

import httpx2

from mesbah.think import ThinkingStream

type PieceKind = Literal["thinking", "content", "finish", "usage"]
type Json = dict[str, object]


@dataclass(frozen=True)
class Endpoint:
    base_url: str
    token: str | None = None


@dataclass(frozen=True)
class Piece:
    kind: PieceKind
    text: str = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class EngineError(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(detail or code)
        self.code: str = code
        self.detail: str = detail


class EngineClient:
    transport: ClassVar[httpx2.BaseTransport | None] = None
    async_transport: ClassVar[httpx2.AsyncBaseTransport | None] = None
    CHECK_TIMEOUT: ClassVar[float] = 3.0
    LOAD_TIMEOUT: ClassVar[float] = 1800.0
    STREAM_TIMEOUT: ClassVar[httpx2.Timeout] = httpx2.Timeout(10.0, read=600.0)

    def __init__(self, endpoint: Endpoint) -> None:
        self.endpoint: Endpoint = endpoint

    def health(self) -> bool:
        try:
            with self._client(self.CHECK_TIMEOUT) as client:
                return client.get("/health").is_success
        except httpx2.HTTPError:
            return False

    def status(self) -> Json:
        return self._call("GET", "/admin/status", self.CHECK_TIMEOUT)

    def load(self, spec: Json) -> Json:
        return self._call("POST", "/admin/load", self.LOAD_TIMEOUT, spec)

    def unload(self) -> Json:
        return self._call("POST", "/admin/unload", self.LOAD_TIMEOUT)

    def models(self) -> list[Json]:
        listed: object = self._call("GET", "/v1/models", self.CHECK_TIMEOUT).get("data")
        return (
            [cast(Json, row) for row in listed if isinstance(row, dict)]
            if isinstance(listed, list)
            else []
        )

    def get(self, path: str) -> Json:
        return self._call("GET", path, self.CHECK_TIMEOUT)

    def post(self, path: str, body: Json, timeout: float | None = None) -> Json:
        return self._call("POST", path, timeout or self.LOAD_TIMEOUT, body)

    def has(self, path: str) -> bool:
        try:
            with self._client(self.CHECK_TIMEOUT) as client:
                return client.head(path).is_success
        except httpx2.HTTPError as error:
            raise EngineError("engine_unreachable") from error

    def upload(self, path: str, file: Path) -> None:
        try:
            with self._client(self.LOAD_TIMEOUT) as client, file.open("rb") as content:
                response: httpx2.Response = client.post(path, content=content)
        except httpx2.HTTPError as error:
            raise EngineError("engine_unreachable") from error
        if not response.is_success:
            raise _refusal(response)

    async def stream_chat(self, body: Json) -> AsyncIterator[Piece]:
        splitter: ThinkingStream = ThinkingStream()
        request: Json = {**body, "stream": True, "stream_options": {"include_usage": True}}
        try:
            async with (
                httpx2.AsyncClient(
                    base_url=self.endpoint.base_url,
                    headers=self._headers(),
                    timeout=self.STREAM_TIMEOUT,
                    transport=type(self).async_transport,
                ) as client,
                client.stream("POST", "/v1/chat/completions", json=request) as response,
            ):
                if not response.is_success:
                    await response.aread()
                    raise _refusal(response)
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data: str = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        break
                    for piece in _pieces(json.loads(data), splitter):
                        yield piece
        except httpx2.TimeoutException as error:
            raise EngineError("engine_timeout") from error
        except httpx2.HTTPError as error:
            raise EngineError("engine_unreachable") from error
        for kind, text in splitter.close():
            yield Piece(kind, text)

    def _call(self, method: str, path: str, timeout: float, body: Json | None = None) -> Json:
        try:
            with self._client(timeout) as client:
                response: httpx2.Response = client.request(method, path, json=body)
        except httpx2.TimeoutException as error:
            raise EngineError("engine_timeout") from error
        except httpx2.HTTPError as error:
            raise EngineError("engine_unreachable") from error
        if not response.is_success:
            raise _refusal(response)
        try:
            payload: object = response.json()
        except ValueError:
            return {}
        return cast(Json, payload) if isinstance(payload, dict) else {}

    def _client(self, timeout: float) -> httpx2.Client:
        return httpx2.Client(
            base_url=self.endpoint.base_url,
            headers=self._headers(),
            timeout=timeout,
            transport=type(self).transport,
        )

    def _headers(self) -> dict[str, str]:
        token: str | None = self.endpoint.token
        return {"Authorization": f"Bearer {token}"} if token else {}


def _refusal(response: httpx2.Response) -> EngineError:
    try:
        payload: object = response.json()
    except ValueError:
        payload = None
    error: object = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        return _failure(cast(Json, error))
    if response.status_code == httpx2.codes.UNAUTHORIZED:
        return EngineError("engine_rejected_token")
    return EngineError("engine_failed", f"HTTP {response.status_code}")


def _failure(error: Json) -> EngineError:
    code: object = error.get("code")
    message: object = error.get("message")
    return EngineError(
        code if isinstance(code, str) and code else "engine_failed",
        message if isinstance(message, str) else "",
    )


def _pieces(chunk: object, splitter: ThinkingStream) -> list[Piece]:
    if not isinstance(chunk, dict):
        return []
    failed: object = chunk.get("error")
    if isinstance(failed, dict):
        raise _failure(cast(Json, failed))
    pieces: list[Piece] = []
    choices: object = chunk.get("choices")
    first: object = choices[0] if isinstance(choices, list) and choices else None
    if isinstance(first, dict):
        delta: object = first.get("delta")
        if isinstance(delta, dict):
            reasoning: object = delta.get("reasoning_content") or delta.get("reasoning")
            if isinstance(reasoning, str) and reasoning:
                pieces.append(Piece("thinking", reasoning))
            content: object = delta.get("content")
            if isinstance(content, str) and content:
                pieces.extend(Piece(kind, text) for kind, text in splitter.feed(content))
        finish: object = first.get("finish_reason")
        if isinstance(finish, str) and finish:
            pieces.append(Piece("finish", finish))
    usage: object = chunk.get("usage")
    if isinstance(usage, dict):
        pieces.append(
            Piece(
                "usage",
                prompt_tokens=_count(usage.get("prompt_tokens")),
                completion_tokens=_count(usage.get("completion_tokens")),
            )
        )
    return pieces


def _count(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
