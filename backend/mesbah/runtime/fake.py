from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

from mesbah.runtime.engine import Engine, Generation
from mesbah.runtime.errors import GenerationFailed, LoadFailed, NotLoaded, UnknownModel
from mesbah.runtime.specs import BASE, ChatRequest, LoadSpec

DELAY_VARIABLE: str = "MESBAH_FAKE_ENGINE_DELAY"
DEFAULT_DELAY: float = 0.05
LONG: str = "[long]"
FAIL: str = "[fail]"
LONG_WORDS: int = 600
FAIL_AFTER: int = 3
WORD: re.Pattern[str] = re.compile(r"\S+\s*")


def asked(request: ChatRequest) -> str:
    users: list[str] = [message.content for message in request.messages if message.role == "user"]
    return users[-1].strip() if users else ""


def answer(request: ChatRequest) -> str:
    question: str = asked(request)
    reply: str = f"Reply from {request.model}: {question}"
    if LONG in question:
        reply += "".join(f" word{number}" for number in range(1, LONG_WORDS + 1))
    return reply


def script(request: ChatRequest) -> list[str]:
    pieces: list[str] = WORD.findall(answer(request))
    if request.enable_thinking is False:
        return pieces
    return ["<think>", "Thinking about: ", asked(request), "</think>", *pieces]


@dataclass
class Loaded:
    spec: LoadSpec
    adapters: dict[str, str] = field(default_factory=dict)


class FakeGeneration(Generation):
    def __init__(self, engine: FakeEngine, request: ChatRequest, stop: threading.Event) -> None:
        super().__init__(engine, request, stop)
        self.delay: float = engine.delay
        self.pieces: list[str] = script(request)
        self.fails_after: int | None = FAIL_AFTER if FAIL in asked(request) else None
        self.sent: int = 0

    def begin(self) -> None:
        if self._state == "new":
            self._state = "running"
            self.prompt_tokens = sum(
                len(message.content.split()) for message in self.request.messages
            )

    def __next__(self) -> str:
        self.begin()
        if self._state != "running" or self._stop.is_set():
            raise StopIteration
        if self.fails_after is not None and self.sent >= self.fails_after:
            self._state = "done"
            raise GenerationFailed("Generation stopped: the fake engine was asked to fail.")
        if self.sent >= len(self.pieces) or self.completion_tokens >= self.request.max_tokens:
            if self.sent < len(self.pieces):
                self.finish_reason = "length"
            self._state = "done"
            raise StopIteration
        self._stop.wait(self.delay)
        piece: str = self.pieces[self.sent]
        self.sent += 1
        self.completion_tokens += 1
        return piece

    def close(self) -> None:
        self._state = "done"


class FakeEngine(Engine):
    def __init__(self, delay: float | None = None) -> None:
        super().__init__()
        self.delay: float = (
            delay if delay is not None else float(os.environ.get(DELAY_VARIABLE, DEFAULT_DELAY))
        )
        self.loaded: Loaded | None = None

    def load(self, spec: LoadSpec) -> None:
        if not Path(spec.base).is_dir():
            raise LoadFailed(f"There is no model folder at {spec.base}.")
        for adapter in spec.adapters:
            if not (Path(adapter.path) / "adapter_config.json").is_file():
                raise LoadFailed(f"There is no adapter at {adapter.path}.")
        if self.loaded is None or not self.loaded.spec.same_base(spec):
            self.loaded = Loaded(spec)
        self.loaded.adapters.update({adapter.name: adapter.path for adapter in spec.adapters})

    def unload(self) -> None:
        self.loaded = None

    def models(self) -> tuple[str, ...]:
        return () if self.loaded is None else (BASE, *list(self.loaded.adapters))

    def status(self) -> dict[str, object]:
        loaded: Loaded | None = self.loaded
        if loaded is None:
            return {"loaded": False, "busy": False}
        return {
            "loaded": True,
            "busy": False,
            "base": loaded.spec.base,
            "architecture": loaded.spec.architecture,
            "quantized": False,
            "device": "cpu",
            "adapters": [{"name": name, "path": path} for name, path in loaded.adapters.items()],
        }

    def generate(self, request: ChatRequest, stop: threading.Event) -> Generation:
        if self.loaded is None:
            raise NotLoaded("No model is loaded.")
        if request.model not in self.models():
            raise UnknownModel(f"The model `{request.model}` does not exist.")
        return FakeGeneration(self, request, stop)
