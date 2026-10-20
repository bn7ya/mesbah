from __future__ import annotations

import json
import math
import os
import struct
import time
from collections.abc import Mapping
from pathlib import Path

from mesbah.train.contract import (
    DeltaStats,
    EventWriter,
    Failure,
    Hyperparams,
    JsonObject,
    JsonValue,
    LayerDelta,
    Metrics,
    Status,
    TrainConfig,
    write_status,
)
from mesbah.train.data import Conversation, Row, Rows, load_rows
from mesbah.train.deltas import ADAPTER_CONFIG, ADAPTER_WEIGHTS, adapter_size_bytes, lora_scale

type Matrix = list[list[float]]

KNOBS: str = "MESBAH_FAKE_TRAINER"
SLOW_STEP_SECONDS: float = 1.0
STEPS: int = 4
HIDDEN: int = 8
LAYERS: int = 2
MODULES: tuple[str, ...] = ("q_proj", "v_proj")
START_LOSS: float = 2.4
F32_BYTES: int = 4
MODEL_CONFIG: str = "config.json"
MODEL_WEIGHTS: str = "model.safetensors"


def knobs() -> frozenset[str]:
    return frozenset(
        part.strip().lower() for part in os.environ.get(KNOBS, "").split(",") if part.strip()
    )


def _tokens(row: Row) -> int:
    if isinstance(row, Conversation):
        return sum(
            len(message.content.split()) + len((message.thinking or "").split())
            for message in row.messages
        )
    return len(row.text.split())


def _key(layer: int, module: str, side: str) -> str:
    return f"base_model.model.model.layers.{layer}.self_attn.{module}.lora_{side}.weight"


def _matrix(rows: int, columns: int, phase: float, size: float) -> Matrix:
    return [
        [size * math.sin(phase + row * 1.7 + column * 0.9) for column in range(columns)]
        for row in range(rows)
    ]


def adapter_tensors(settings: Hyperparams, steps: int) -> dict[str, Matrix]:
    tensors: dict[str, Matrix] = {}
    for layer in range(LAYERS):
        for offset, module in enumerate(MODULES):
            phase: float = settings.seed + layer * 3.1 + offset * 0.7
            tensors[_key(layer, module, "A")] = _matrix(settings.lora_rank, HIDDEN, phase, 0.1)
            tensors[_key(layer, module, "B")] = _matrix(
                HIDDEN, settings.lora_rank, phase + 0.5, 0.002 * steps
            )
    return tensors


def write_safetensors(path: Path, tensors: Mapping[str, Matrix]) -> None:
    header: JsonObject = {"__metadata__": {"format": "pt"}}
    blobs: list[bytes] = []
    offset: int = 0
    for name in sorted(tensors):
        matrix: Matrix = tensors[name]
        flat: list[float] = [value for row in matrix for value in row]
        blob: bytes = struct.pack(f"<{len(flat)}f", *flat)
        header[name] = {
            "dtype": "F32",
            "shape": [len(matrix), len(matrix[0]) if matrix else 0],
            "data_offsets": [offset, offset + len(blob)],
        }
        blobs.append(blob)
        offset += len(blob)
    encoded: bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    encoded += b" " * (-len(encoded) % 8)
    path.write_bytes(struct.pack("<Q", len(encoded)) + encoded + b"".join(blobs))


def read_safetensors(path: Path) -> dict[str, Matrix]:
    raw: bytes = path.read_bytes()
    (length,) = struct.unpack("<Q", raw[:8])
    header: object = json.loads(raw[8 : 8 + length])
    if not isinstance(header, dict):
        raise ValueError(f"{path} has no safetensors header")
    body: bytes = raw[8 + length :]
    tensors: dict[str, Matrix] = {}
    for name, entry in header.items():
        if name == "__metadata__":
            continue
        if entry["dtype"] != "F32" or len(entry["shape"]) != 2:
            raise ValueError(f"{name} is not a float32 matrix")
        rows, columns = int(entry["shape"][0]), int(entry["shape"][1])
        start, end = int(entry["data_offsets"][0]), int(entry["data_offsets"][1])
        flat: tuple[float, ...] = struct.unpack(f"<{(end - start) // F32_BYTES}f", body[start:end])
        tensors[str(name)] = [
            list(flat[row * columns : (row + 1) * columns]) for row in range(rows)
        ]
    return tensors


def _delta(b: Matrix, a: Matrix, scale: float) -> Matrix:
    return [
        [
            scale * sum(b[row][k] * a[k][column] for k in range(len(a)))
            for column in range(len(a[0]))
        ]
        for row in range(len(b))
    ]


def _dense(tensors: Mapping[str, Matrix], scale: float) -> dict[str, Matrix]:
    modules: dict[str, Matrix] = {}
    for key, a in tensors.items():
        if key.endswith(".lora_A.weight"):
            name: str = key.removesuffix(".lora_A.weight")
            modules[name] = _delta(tensors[f"{name}.lora_B.weight"], a, scale)
    return modules


def _norm(matrix: Matrix) -> float:
    return math.sqrt(sum(value * value for row in matrix for value in row))


def _difference(first: Matrix, second: Matrix) -> Matrix:
    return [
        [x - y for x, y in zip(top, bottom, strict=True)]
        for top, bottom in zip(first, second, strict=True)
    ]


def _parent_change(dense: Mapping[str, Matrix], parent_dir: Path) -> float | None:
    try:
        settings: object = json.loads((parent_dir / ADAPTER_CONFIG).read_text(encoding="utf-8"))
        tensors: dict[str, Matrix] = read_safetensors(parent_dir / ADAPTER_WEIGHTS)
    except (OSError, ValueError, KeyError, TypeError, struct.error):
        return None
    if not isinstance(settings, dict):
        return None
    rank: int = int(settings.get("r", 1))
    scale: float = lora_scale(
        float(settings.get("lora_alpha", rank)), rank, settings.get("use_rslora") is True
    )
    parent: dict[str, Matrix] = _dense(tensors, scale)
    empty: Matrix = [[0.0] * HIDDEN for _ in range(HIDDEN)]
    return math.sqrt(
        sum(
            _norm(_difference(dense.get(name, empty), parent.get(name, empty))) ** 2
            for name in dense.keys() | parent.keys()
        )
    )


def write_model(config: TrainConfig) -> int:
    output: Path = Path(config.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    settings: JsonObject = dict(config.model_config or {})
    (output / MODEL_CONFIG).write_text(json.dumps(settings, indent=2), encoding="utf-8")
    seed: float = config.hyperparams.seed
    tensors: dict[str, Matrix] = {
        "model.embed_tokens.weight": _matrix(HIDDEN, HIDDEN, seed, 0.02),
        "model.norm.weight": [[1.0] * HIDDEN],
    }
    write_safetensors(output / MODEL_WEIGHTS, tensors)
    return sum(len(matrix) * len(matrix[0]) for matrix in tensors.values())


def write_adapter(config: TrainConfig, steps: int) -> DeltaStats:
    settings: Hyperparams = config.hyperparams
    output: Path = Path(config.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    tensors: dict[str, Matrix] = adapter_tensors(settings, steps)
    write_safetensors(output / ADAPTER_WEIGHTS, tensors)
    adapter_config: JsonObject = {
        "peft_type": "LORA",
        "task_type": "CAUSAL_LM",
        "base_model_name_or_path": config.base.repo_id,
        "r": settings.lora_rank,
        "lora_alpha": settings.lora_alpha,
        "lora_dropout": settings.lora_dropout,
        "use_rslora": settings.use_rslora,
        "bias": "none",
        "target_modules": list[JsonValue](MODULES),
        "rank_pattern": {},
        "alpha_pattern": {},
    }
    (output / ADAPTER_CONFIG).write_text(json.dumps(adapter_config, indent=2), encoding="utf-8")
    scale: float = lora_scale(settings.lora_alpha, settings.lora_rank, settings.use_rslora)
    dense: dict[str, Matrix] = _dense(tensors, scale)
    layers: list[LayerDelta] = [
        LayerDelta(
            name=name.removeprefix("base_model.model."),
            layer=int(name.split(".layers.")[1].split(".")[0]),
            module=name.rsplit(".", 1)[-1],
            norm=_norm(matrix),
        )
        for name, matrix in sorted(dense.items())
    ]
    return DeltaStats(
        layers=tuple(layers),
        total_norm=math.sqrt(sum(layer.norm**2 for layer in layers)),
        parameters=sum(len(matrix) * len(matrix[0]) for matrix in tensors.values()),
        rank=settings.lora_rank,
        change_from_parent=(
            None
            if config.parent_adapter is None
            else _parent_change(dense, Path(config.parent_adapter))
        ),
    )


def _metrics(rows: Rows | None, steps: int, loss: float | None, started: float) -> Metrics:
    return Metrics(
        final_loss=loss,
        steps=steps,
        examples=0 if rows is None else len(rows.rows),
        skipped=0 if rows is None else rows.skipped,
        seconds=round(time.monotonic() - started, 3),
    )


def _fail(events: EventWriter, failure: Failure, metrics: Metrics) -> Status:
    events.error(failure.code, failure.detail)
    return Status(status="failed", error=failure, metrics=metrics)


def _train(config: TrainConfig, events: EventWriter, started: float) -> Status:
    flags: frozenset[str] = knobs()
    settings: Hyperparams = config.hyperparams
    cancel: Path = Path(config.cancel_path)
    events.loading("data")
    rows: Rows = load_rows(config.examples)
    events.loading("tokenizer")
    events.data(examples=len(rows.rows), skipped=rows.skipped, tokens=sum(map(_tokens, rows.rows)))
    if not rows.rows:
        failure: Failure = Failure("no_examples", "the example files hold no usable row")
        return _fail(events, failure, _metrics(rows, 0, None, started))
    events.loading("model")
    total: int = settings.max_steps or STEPS
    events.begin(total_steps=total)
    if "oom" in flags:
        events.oom_retry(max_seq_len=max(256, settings.max_seq_len // 2))
        failure = Failure("out_of_memory", "fake trainer: CUDA out of memory")
        return _fail(events, failure, _metrics(rows, 0, None, started))
    loss: float | None = None
    for step in range(1, total + 1):
        if cancel.exists():
            return Status(status="cancelled", metrics=_metrics(rows, step - 1, loss, started))
        if "slow" in flags:
            time.sleep(SLOW_STEP_SECONDS)
        loss = round(START_LOSS * 0.85**step, 4)
        events.log(
            step=step,
            total_steps=total,
            epoch=round(settings.epochs * step / total, 4),
            loss=loss,
            learning_rate=settings.learning_rate * (1 - (step - 1) / total),
            grad_norm=round(1.5 * 0.9**step, 4),
        )
        if "fail" in flags:
            failure = Failure("failed", "fake trainer: failed on purpose")
            return _fail(events, failure, _metrics(rows, step, loss, started))
    if cancel.exists():
        return Status(status="cancelled", metrics=_metrics(rows, total, loss, started))
    events.saving()
    output: Path = Path(config.output_dir)
    status: Status
    if config.kind == "pretrain":
        parameters: int = write_model(config)
        status = Status(
            status="completed",
            model_dir=str(output),
            size_bytes=adapter_size_bytes(output),
            parameters=parameters,
            metrics=_metrics(rows, total, loss, started),
        )
    else:
        delta: DeltaStats = write_adapter(config, total)
        status = Status(
            status="completed",
            adapter_dir=str(output),
            size_bytes=adapter_size_bytes(output),
            delta=delta,
            metrics=_metrics(rows, total, loss, started),
        )
    events.done()
    return status


def run(config: TrainConfig) -> Status:
    started: float = time.monotonic()
    events: EventWriter = EventWriter(Path(config.events_path))
    status: Status
    try:
        status = _train(config, events, started)
    except KeyboardInterrupt:
        status = Status(status="cancelled", metrics=_metrics(None, 0, None, started))
    except Exception as exc:  # noqa: BLE001 - every failure ends as a failed status
        failure: Failure = Failure("failed", f"{type(exc).__name__}: {exc}")
        status = _fail(events, failure, _metrics(None, 0, None, started))
    write_status(Path(config.status_path), status)
    return status
