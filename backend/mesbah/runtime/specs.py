from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from mesbah.runtime.errors import InvalidRequest

type Role = Literal["system", "user", "assistant"]
type Architecture = Literal["causal", "seq2seq"]
type Json = dict[str, object]

BASE: str = "base"
ROLES: tuple[Role, ...] = ("system", "user", "assistant")
ARCHITECTURES: tuple[Architecture, ...] = ("causal", "seq2seq")
DEFAULT_MAX_TOKENS: int = 2048


def _object(value: object, where: str) -> Json:
    if not isinstance(value, dict):
        raise InvalidRequest(f"{where} must be a JSON object.")
    return cast(Json, value)


def _list(data: Json, key: str) -> list[object]:
    value: object = data.get(key, [])
    if not isinstance(value, list):
        raise InvalidRequest(f"`{key}` must be a list.")
    return cast(list[object], value)


def _name(data: Json, key: str, where: str) -> str:
    value: object = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InvalidRequest(f"{where}: `{key}` must be a non-empty string.")
    return value


def _flag(data: Json, key: str, default: bool | None) -> bool | None:
    value: object = data.get(key, default)
    if value is not None and not isinstance(value, bool):
        raise InvalidRequest(f"`{key}` must be true or false.")
    return value


def _number(data: Json, key: str) -> float | None:
    value: object = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise InvalidRequest(f"`{key}` must be a number.")
    return float(value)


def _whole(value: object, what: str, least: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < least:
        raise InvalidRequest(f"{what} must be a whole number of at least {least}.")
    return value


@dataclass(frozen=True)
class AdapterSpec:
    name: str
    path: str

    @classmethod
    def from_json(cls, value: object) -> AdapterSpec:
        data: Json = _object(value, "An adapter")
        name: str = _name(data, "name", "An adapter")
        if name == BASE:
            raise InvalidRequest(f"`{BASE}` names the base model; an adapter needs another name.")
        return cls(name=name, path=_name(data, "path", f"Adapter {name}"))


@dataclass(frozen=True)
class LoadSpec:
    base: str
    architecture: Architecture = "causal"
    quantize_4bit: bool = False
    gpu_indices: tuple[int, ...] = ()
    adapters: tuple[AdapterSpec, ...] = ()

    @classmethod
    def from_json(cls, value: object) -> LoadSpec:
        data: Json = _object(value, "The load request")
        architecture: object = data.get("architecture", "causal")
        if architecture not in ARCHITECTURES:
            raise InvalidRequest(f"`architecture` must be one of {', '.join(ARCHITECTURES)}.")
        gpus: tuple[int, ...] = tuple(
            _whole(index, "A GPU index", 0) for index in _list(data, "gpu_indices")
        )
        adapters: tuple[AdapterSpec, ...] = tuple(
            AdapterSpec.from_json(adapter) for adapter in _list(data, "adapters")
        )
        if len({adapter.name for adapter in adapters}) < len(adapters):
            raise InvalidRequest("Two adapters share a name.")
        if len(set(gpus)) < len(gpus):
            raise InvalidRequest("A GPU index is listed twice.")
        return cls(
            base=_name(data, "base", "The load request"),
            architecture=cast(Architecture, architecture),
            quantize_4bit=bool(_flag(data, "quantize_4bit", False)),
            gpu_indices=gpus,
            adapters=adapters,
        )

    def same_base(self, other: LoadSpec) -> bool:
        return (self.base, self.architecture, self.quantize_4bit, self.gpu_indices) == (
            other.base,
            other.architecture,
            other.quantize_4bit,
            other.gpu_indices,
        )


@dataclass(frozen=True)
class ChatMessage:
    role: Role
    content: str
    reasoning_content: str | None = None

    @classmethod
    def from_json(cls, value: object) -> ChatMessage:
        data: Json = _object(value, "A message")
        role: object = data.get("role")
        if role not in ROLES:
            raise InvalidRequest(f"A message's `role` must be one of {', '.join(ROLES)}.")
        content: object = data.get("content")
        if not isinstance(content, str):
            raise InvalidRequest("A message's `content` must be a string.")
        reasoning: object = data.get("reasoning_content")
        if reasoning is not None and (role != "assistant" or not isinstance(reasoning, str)):
            raise InvalidRequest("`reasoning_content` is a string, on assistant messages only.")
        return cls(role=cast(Role, role), content=content, reasoning_content=reasoning)

    def for_template(self) -> dict[str, str]:
        message: dict[str, str] = {"role": self.role, "content": self.content}
        if self.reasoning_content is not None:
            message["reasoning_content"] = self.reasoning_content
        return message


@dataclass(frozen=True)
class ChatRequest:
    model: str
    messages: tuple[ChatMessage, ...]
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int = DEFAULT_MAX_TOKENS
    stream: bool = False
    enable_thinking: bool | None = None

    @classmethod
    def from_json(cls, value: object) -> ChatRequest:
        data: Json = _object(value, "The request")
        messages: tuple[ChatMessage, ...] = tuple(
            ChatMessage.from_json(message) for message in _list(data, "messages")
        )
        if not messages:
            raise InvalidRequest("`messages` must hold at least one message.")
        top_p: float | None = _number(data, "top_p")
        if top_p is not None and not 0 < top_p <= 1:
            raise InvalidRequest("`top_p` must be above 0 and at most 1.")
        limit: object = data.get("max_tokens")
        options: object = data.get("chat_template_kwargs")
        thinking: bool | None = None
        if options is not None:
            thinking = _flag(_object(options, "`chat_template_kwargs`"), "enable_thinking", None)
        return cls(
            model=_name(data, "model", "The request"),
            messages=messages,
            temperature=_number(data, "temperature"),
            top_p=top_p,
            max_tokens=DEFAULT_MAX_TOKENS if limit is None else _whole(limit, "`max_tokens`", 1),
            stream=bool(_flag(data, "stream", False)),
            enable_thinking=thinking,
        )
