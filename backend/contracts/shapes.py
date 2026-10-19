from __future__ import annotations

import json
from collections.abc import Iterable

from contracts import canonical

LITERALS: frozenset[str] = frozenset(
    {"object", "owned_by", "finish_reason", "role", "done", "done_reason", "code", "type"}
)
TYPES: tuple[tuple[type, str], ...] = (
    (bool, "boolean"),
    (int, "integer"),
    (float, "number"),
    (str, "string"),
)


def shape(value: object, key: str = "") -> object:
    if isinstance(value, dict):
        return {str(name): shape(item, str(name)) for name, item in value.items()}
    if isinstance(value, list):
        return distinct(shape(item) for item in value)
    if value is None:
        return "null"
    if key in LITERALS and isinstance(value, str | bool):
        return value
    return next(name for kind, name in TYPES if isinstance(value, kind))


def distinct(shapes: Iterable[object]) -> list[object]:
    seen: dict[str, object] = {}
    for each in shapes:
        seen.setdefault(canonical(each), each)
    return list(seen.values())


def events(content_type: str, body: bytes) -> object:
    text: str = body.decode()
    if content_type == "text/event-stream":
        payloads: list[str] = [
            line.removeprefix("data:").strip()
            for line in text.splitlines()
            if line.startswith("data:")
        ]
        return distinct(
            "[DONE]" if payload == "[DONE]" else shape(json.loads(payload)) for payload in payloads
        )
    if content_type == "application/x-ndjson":
        return distinct(shape(json.loads(line)) for line in text.splitlines() if line.strip())
    return shape(json.loads(text)) if text else "empty"
