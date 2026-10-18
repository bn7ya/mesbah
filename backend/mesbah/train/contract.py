from __future__ import annotations

import json
import math
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Self, cast

type JsonValue = str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]
type ErrorCode = Literal["out_of_memory", "no_examples", "load_failed", "failed"]
type RunState = Literal["completed", "failed", "cancelled"]
type EventName = Literal["loading", "data", "begin", "log", "oom_retry", "saving", "done", "error"]

ERROR_CODES: tuple[ErrorCode, ...] = ("out_of_memory", "no_examples", "load_failed", "failed")
RUN_STATES: tuple[RunState, ...] = ("completed", "failed", "cancelled")
ALL_LINEAR: str = "all-linear"
_REQUIRED: object = object()


class ContractError(ValueError):
    pass


def _object(value: object, where: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ContractError(f"{where} must be a JSON object")
    return cast(Mapping[str, object], value)


def _get(data: Mapping[str, object], key: str, default: object = _REQUIRED) -> object:
    if key in data:
        return data[key]
    if default is _REQUIRED:
        raise ContractError(f"{key!r} is missing")
    return default


def _str(value: object, key: str) -> str:
    if not isinstance(value, str):
        raise ContractError(f"{key!r} must be a string")
    return value


def _optional_str(value: object, key: str) -> str | None:
    return None if value is None else _str(value, key)


def _int(value: object, key: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError(f"{key!r} must be an integer")
    return value


def _optional_int(value: object, key: str) -> int | None:
    return None if value is None else _int(value, key)


def _float(value: object, key: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ContractError(f"{key!r} must be a number")
    return float(value)


def _optional_float(value: object, key: str) -> float | None:
    return None if value is None else _float(value, key)


def _bool(value: object, key: str) -> bool:
    if not isinstance(value, bool):
        raise ContractError(f"{key!r} must be true or false")
    return value


def _list(value: object, key: str) -> list[object]:
    if not isinstance(value, list):
        raise ContractError(f"{key!r} must be a list")
    return cast(list[object], value)


def _choice[T: str](value: object, key: str, choices: tuple[T, ...]) -> T:
    text: str = _str(value, key)
    for choice in choices:
        if text == choice:
            return choice
    raise ContractError(f"{key!r} must be one of {', '.join(choices)}")


def finite(value: float | None) -> float | None:
    return value if value is not None and math.isfinite(value) else None


def _dump(data: JsonObject) -> str:
    return json.dumps(data, ensure_ascii=False, allow_nan=False)


def _read_object(path: Path) -> Mapping[str, object]:
    try:
        parsed: object = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContractError(f"{path} is not valid JSON: {exc}") from exc
    return _object(parsed, str(path))


def _write_atomically(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial: Path = path.with_name(f".{path.name}.partial")
    partial.write_text(text, encoding="utf-8")
    os.replace(partial, path)


@dataclass(frozen=True)
class BaseModelRef:
    repo_id: str
    path: str | None = None
    revision: str | None = None

    @property
    def source(self) -> str:
        return self.path or self.repo_id

    @classmethod
    def from_json(cls, data: object) -> Self:
        found: Mapping[str, object] = _object(data, "base")
        return cls(
            repo_id=_str(_get(found, "repo_id"), "repo_id"),
            path=_optional_str(_get(found, "path", None), "path"),
            revision=_optional_str(_get(found, "revision", None), "revision"),
        )

    def to_json(self) -> JsonObject:
        return {"repo_id": self.repo_id, "path": self.path, "revision": self.revision}


@dataclass(frozen=True)
class ExampleSource:
    path: str
    max_rows: int | None = None

    @classmethod
    def from_json(cls, data: object) -> Self:
        found: Mapping[str, object] = _object(data, "examples[]")
        max_rows: int | None = _optional_int(_get(found, "max_rows", None), "max_rows")
        if max_rows is not None and max_rows < 0:
            raise ContractError("'max_rows' must not be negative")
        return cls(path=_str(_get(found, "path"), "path"), max_rows=max_rows)

    def to_json(self) -> JsonObject:
        return {"path": self.path, "max_rows": self.max_rows}


@dataclass(frozen=True)
class Hyperparams:
    epochs: float = 1.0
    max_steps: int | None = None
    learning_rate: float = 2e-4
    lora_rank: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.0
    use_rslora: bool = False
    target_modules: str | tuple[str, ...] = ALL_LINEAR
    train_biases: bool = False
    max_seq_len: int = 2048
    batch_size: int = 1
    grad_accum: int = 8
    warmup_ratio: float = 0.03
    lr_scheduler: str = "cosine"
    seed: int = 42
    quantize_4bit: bool = True
    gradient_checkpointing: bool = True

    def __post_init__(self) -> None:
        positive: dict[str, float] = {
            "epochs": self.epochs,
            "learning_rate": self.learning_rate,
            "lora_rank": self.lora_rank,
            "lora_alpha": self.lora_alpha,
            "max_seq_len": self.max_seq_len,
            "batch_size": self.batch_size,
            "grad_accum": self.grad_accum,
        }
        for key, value in positive.items():
            if value <= 0:
                raise ContractError(f"{key!r} must be positive")
        if self.max_steps is not None and self.max_steps < 1:
            raise ContractError("'max_steps' must be at least 1")
        if not 0 <= self.lora_dropout < 1:
            raise ContractError("'lora_dropout' must be in [0, 1)")
        if not 0 <= self.warmup_ratio < 1:
            raise ContractError("'warmup_ratio' must be in [0, 1)")
        if isinstance(self.target_modules, tuple) and not self.target_modules:
            raise ContractError("'target_modules' must name at least one module")

    @classmethod
    def from_json(cls, data: object) -> Self:
        found: Mapping[str, object] = _object(data, "hyperparams")
        defaults: Hyperparams = Hyperparams()
        targets: object = _get(found, "target_modules", defaults.target_modules)
        target_modules: str | tuple[str, ...] = (
            targets
            if isinstance(targets, str)
            else tuple(_str(name, "target_modules[]") for name in _list(targets, "target_modules"))
        )
        return cls(
            epochs=_float(_get(found, "epochs", defaults.epochs), "epochs"),
            max_steps=_optional_int(_get(found, "max_steps", None), "max_steps"),
            learning_rate=_float(
                _get(found, "learning_rate", defaults.learning_rate), "learning_rate"
            ),
            lora_rank=_int(_get(found, "lora_rank", defaults.lora_rank), "lora_rank"),
            lora_alpha=_int(_get(found, "lora_alpha", defaults.lora_alpha), "lora_alpha"),
            lora_dropout=_float(_get(found, "lora_dropout", defaults.lora_dropout), "lora_dropout"),
            use_rslora=_bool(_get(found, "use_rslora", defaults.use_rslora), "use_rslora"),
            target_modules=target_modules,
            train_biases=_bool(_get(found, "train_biases", defaults.train_biases), "train_biases"),
            max_seq_len=_int(_get(found, "max_seq_len", defaults.max_seq_len), "max_seq_len"),
            batch_size=_int(_get(found, "batch_size", defaults.batch_size), "batch_size"),
            grad_accum=_int(_get(found, "grad_accum", defaults.grad_accum), "grad_accum"),
            warmup_ratio=_float(_get(found, "warmup_ratio", defaults.warmup_ratio), "warmup_ratio"),
            lr_scheduler=_str(_get(found, "lr_scheduler", defaults.lr_scheduler), "lr_scheduler"),
            seed=_int(_get(found, "seed", defaults.seed), "seed"),
            quantize_4bit=_bool(
                _get(found, "quantize_4bit", defaults.quantize_4bit), "quantize_4bit"
            ),
            gradient_checkpointing=_bool(
                _get(found, "gradient_checkpointing", defaults.gradient_checkpointing),
                "gradient_checkpointing",
            ),
        )

    def to_json(self) -> JsonObject:
        targets: JsonValue = (
            self.target_modules
            if isinstance(self.target_modules, str)
            else list[JsonValue](self.target_modules)
        )
        return {
            "epochs": self.epochs,
            "max_steps": self.max_steps,
            "learning_rate": self.learning_rate,
            "lora_rank": self.lora_rank,
            "lora_alpha": self.lora_alpha,
            "lora_dropout": self.lora_dropout,
            "use_rslora": self.use_rslora,
            "target_modules": targets,
            "train_biases": self.train_biases,
            "max_seq_len": self.max_seq_len,
            "batch_size": self.batch_size,
            "grad_accum": self.grad_accum,
            "warmup_ratio": self.warmup_ratio,
            "lr_scheduler": self.lr_scheduler,
            "seed": self.seed,
            "quantize_4bit": self.quantize_4bit,
            "gradient_checkpointing": self.gradient_checkpointing,
        }


@dataclass(frozen=True)
class TrainConfig:
    run_id: str
    base: BaseModelRef
    output_dir: str
    events_path: str
    status_path: str
    cancel_path: str
    examples: tuple[ExampleSource, ...] = ()
    parent_adapter: str | None = None
    hyperparams: Hyperparams = field(default_factory=Hyperparams)
    gpu_indices: tuple[int, ...] = ()

    @classmethod
    def from_json(cls, data: object) -> Self:
        found: Mapping[str, object] = _object(data, "config")
        indices: tuple[int, ...] = tuple(
            _int(index, "gpu_indices[]")
            for index in _list(_get(found, "gpu_indices", []), "gpu_indices")
        )
        if any(index < 0 for index in indices):
            raise ContractError("'gpu_indices' must not be negative")
        return cls(
            run_id=_str(_get(found, "run_id"), "run_id"),
            base=BaseModelRef.from_json(_get(found, "base")),
            parent_adapter=_optional_str(_get(found, "parent_adapter", None), "parent_adapter"),
            examples=tuple(
                ExampleSource.from_json(entry)
                for entry in _list(_get(found, "examples", []), "examples")
            ),
            output_dir=_str(_get(found, "output_dir"), "output_dir"),
            events_path=_str(_get(found, "events_path"), "events_path"),
            status_path=_str(_get(found, "status_path"), "status_path"),
            cancel_path=_str(_get(found, "cancel_path"), "cancel_path"),
            hyperparams=Hyperparams.from_json(_get(found, "hyperparams", {})),
            gpu_indices=indices,
        )

    def to_json(self) -> JsonObject:
        written: JsonObject = {
            "run_id": self.run_id,
            "base": self.base.to_json(),
            "parent_adapter": self.parent_adapter,
            "examples": [source.to_json() for source in self.examples],
            "output_dir": self.output_dir,
            "events_path": self.events_path,
            "status_path": self.status_path,
            "cancel_path": self.cancel_path,
            "hyperparams": self.hyperparams.to_json(),
            "gpu_indices": list[JsonValue](self.gpu_indices),
        }
        return written

    @classmethod
    def read(cls, path: Path) -> Self:
        return cls.from_json(_read_object(path))

    def write(self, path: Path) -> None:
        _write_atomically(path, _dump(self.to_json()))


@dataclass(frozen=True)
class Failure:
    code: ErrorCode
    detail: str

    @classmethod
    def from_json(cls, data: object) -> Self:
        found: Mapping[str, object] = _object(data, "error")
        return cls(
            code=_choice(_get(found, "code"), "code", ERROR_CODES),
            detail=_str(_get(found, "detail", ""), "detail"),
        )

    def to_json(self) -> JsonObject:
        return {"code": self.code, "detail": self.detail}


@dataclass(frozen=True)
class Metrics:
    final_loss: float | None = None
    steps: int = 0
    examples: int = 0
    skipped: int = 0
    seconds: float = 0.0

    @classmethod
    def from_json(cls, data: object) -> Self:
        found: Mapping[str, object] = _object(data, "metrics")
        return cls(
            final_loss=_optional_float(_get(found, "final_loss", None), "final_loss"),
            steps=_int(_get(found, "steps", 0), "steps"),
            examples=_int(_get(found, "examples", 0), "examples"),
            skipped=_int(_get(found, "skipped", 0), "skipped"),
            seconds=_float(_get(found, "seconds", 0.0), "seconds"),
        )

    def to_json(self) -> JsonObject:
        return {
            "final_loss": finite(self.final_loss),
            "steps": self.steps,
            "examples": self.examples,
            "skipped": self.skipped,
            "seconds": self.seconds,
        }


@dataclass(frozen=True)
class LayerDelta:
    name: str
    layer: int | None
    module: str
    norm: float

    @classmethod
    def from_json(cls, data: object) -> Self:
        found: Mapping[str, object] = _object(data, "layers[]")
        return cls(
            name=_str(_get(found, "name"), "name"),
            layer=_optional_int(_get(found, "layer", None), "layer"),
            module=_str(_get(found, "module"), "module"),
            norm=_float(_get(found, "norm"), "norm"),
        )

    def to_json(self) -> JsonObject:
        return {"name": self.name, "layer": self.layer, "module": self.module, "norm": self.norm}


@dataclass(frozen=True)
class DeltaStats:
    layers: tuple[LayerDelta, ...]
    total_norm: float
    parameters: int
    rank: int
    change_from_parent: float | None = None

    @classmethod
    def from_json(cls, data: object) -> Self:
        found: Mapping[str, object] = _object(data, "delta")
        return cls(
            layers=tuple(
                LayerDelta.from_json(entry) for entry in _list(_get(found, "layers"), "layers")
            ),
            total_norm=_float(_get(found, "total_norm"), "total_norm"),
            parameters=_int(_get(found, "parameters"), "parameters"),
            rank=_int(_get(found, "rank"), "rank"),
            change_from_parent=_optional_float(
                _get(found, "change_from_parent", None), "change_from_parent"
            ),
        )

    def to_json(self) -> JsonObject:
        return {
            "layers": [layer.to_json() for layer in self.layers],
            "total_norm": self.total_norm,
            "parameters": self.parameters,
            "rank": self.rank,
            "change_from_parent": self.change_from_parent,
        }


@dataclass(frozen=True)
class Status:
    status: RunState
    metrics: Metrics
    adapter_dir: str | None = None
    size_bytes: int = 0
    delta: DeltaStats | None = None
    error: Failure | None = None

    @classmethod
    def from_json(cls, data: object) -> Self:
        found: Mapping[str, object] = _object(data, "status")
        delta: object = _get(found, "delta", None)
        error: object = _get(found, "error", None)
        return cls(
            status=_choice(_get(found, "status"), "status", RUN_STATES),
            adapter_dir=_optional_str(_get(found, "adapter_dir", None), "adapter_dir"),
            size_bytes=_int(_get(found, "size_bytes", 0), "size_bytes"),
            delta=None if delta is None else DeltaStats.from_json(delta),
            error=None if error is None else Failure.from_json(error),
            metrics=Metrics.from_json(_get(found, "metrics", {})),
        )

    def to_json(self) -> JsonObject:
        return {
            "status": self.status,
            "adapter_dir": self.adapter_dir,
            "size_bytes": self.size_bytes,
            "delta": None if self.delta is None else self.delta.to_json(),
            "error": None if self.error is None else self.error.to_json(),
            "metrics": self.metrics.to_json(),
        }

    @classmethod
    def read(cls, path: Path) -> Self:
        return cls.from_json(_read_object(path))


def write_status(path: Path, status: Status) -> None:
    _write_atomically(path, _dump(status.to_json()))


class EventWriter:
    def __init__(self, path: Path) -> None:
        self.path: Path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: EventName, **fields: JsonValue) -> None:
        line: str = _dump({"ts": time.time(), "event": event, **fields})
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
            stream.flush()

    def loading(self, stage: str) -> None:
        self.emit("loading", stage=stage)

    def data(self, examples: int, skipped: int, tokens: int) -> None:
        self.emit("data", examples=examples, skipped=skipped, tokens=tokens)

    def begin(self, total_steps: int) -> None:
        self.emit("begin", total_steps=total_steps)

    def log(
        self,
        step: int,
        total_steps: int,
        epoch: float | None,
        loss: float | None,
        learning_rate: float | None,
        grad_norm: float | None,
    ) -> None:
        self.emit(
            "log",
            step=step,
            total_steps=total_steps,
            epoch=finite(epoch),
            loss=finite(loss),
            learning_rate=finite(learning_rate),
            grad_norm=finite(grad_norm),
        )

    def oom_retry(self, max_seq_len: int) -> None:
        self.emit("oom_retry", max_seq_len=max_seq_len)

    def saving(self) -> None:
        self.emit("saving")

    def done(self) -> None:
        self.emit("done")

    def error(self, code: ErrorCode, detail: str) -> None:
        self.emit("error", code=code, detail=detail)


def read_events(path: Path) -> list[JsonObject]:
    if not path.exists():
        return []
    found: list[JsonObject] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            parsed: object = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            found.append(cast(JsonObject, parsed))
    return found
