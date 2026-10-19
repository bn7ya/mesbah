from __future__ import annotations

import json
from pathlib import Path

import pytest

from contracts import Contract
from mesbah.export.contract import ExportConfig, ExportStatus
from mesbah.train.contract import (
    DeltaStats,
    EventWriter,
    Failure,
    JsonObject,
    LayerDelta,
    Metrics,
    Status,
    TrainConfig,
    read_events,
)

RUN: JsonObject = {
    "run_id": "run-1",
    "base": {"repo_id": "org/name", "path": "/data/hf/snapshot", "revision": None},
    "examples": [{"path": "/data/runs/run-1/examples.jsonl", "max_rows": 500}],
    "output_dir": "/data/versions/v1",
    "events_path": "/data/runs/run-1/events.jsonl",
    "status_path": "/data/runs/run-1/status.json",
    "cancel_path": "/data/runs/run-1/cancel",
    "gpu_indices": [0],
}
PRETRAIN: JsonObject = {
    **RUN,
    "kind": "pretrain",
    "base": {"repo_id": "local/new-model", "path": None, "revision": None},
    "architecture": "seq2seq",
    "model_config": {"model_type": "t5", "d_model": 64},
    "tokenizer": "org/tokenizer",
    "pretrain": {"optim": "adamw_8bit"},
}
METRICS: Metrics = Metrics(final_loss=1.25, steps=3, examples=2, skipped=1, seconds=0.5)


def statuses() -> dict[str, JsonObject]:
    delta: DeltaStats = DeltaStats(
        layers=(LayerDelta(name="model.layers.0.q_proj", layer=0, module="q_proj", norm=0.5),),
        total_norm=0.5,
        parameters=64,
        rank=4,
        change_from_parent=0.25,
    )
    return {
        "lora": Status("completed", METRICS, "/data/versions/v1", 1234, delta).to_json(),
        "pretrain": Status(
            "completed", METRICS, model_dir="/data/models/trained/new", parameters=9_000
        ).to_json(),
        "failed": Status(
            "failed", METRICS, error=Failure("out_of_memory", "CUDA out of memory")
        ).to_json(),
        "cancelled": Status("cancelled", METRICS).to_json(),
    }


def events(path: Path) -> dict[str, list[str]]:
    writer: EventWriter = EventWriter(path)
    writer.loading("model")
    writer.data(examples=2, skipped=1, tokens=40)
    writer.begin(total_steps=3)
    writer.log(step=1, total_steps=3, epoch=0.3, loss=2.0, learning_rate=1e-4, grad_norm=1.0)
    writer.oom_retry(max_seq_len=1024)
    writer.saving()
    writer.done()
    writer.error("failed", "it broke")
    return {
        str(event["event"]): sorted(key for key in event if key not in {"ts", "event"})
        for event in read_events(path)
    }


def status(written: ExportStatus, folder: Path) -> object:
    path: Path = folder / f"{written.status}.json"
    written.write(path)
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.contract
def test_the_files_django_and_the_trainer_exchange(contract: Contract, tmp_path: Path) -> None:
    contract.check(
        "files.json",
        {
            "train": {
                "config": {
                    "lora": TrainConfig.from_json(RUN).to_json(),
                    "pretrain": TrainConfig.from_json(PRETRAIN).to_json(),
                },
                "status": statuses(),
                "events": events(tmp_path / "events.jsonl"),
            },
            "export": {
                "config": {
                    kind: ExportConfig.from_json(
                        {
                            "kind": kind,
                            "base_path": "/data/hf/snapshot",
                            "adapter_path": "/data/versions/v1",
                            "output_dir": "/data/exports/e1",
                            "status_path": "/data/exports/e1/status.json",
                            "tools_dir": "/data/tools",
                            "out_type": "q8_0",
                        }
                    ).to_json()
                    for kind in ("merged", "gguf")
                },
                "status": {
                    "completed": status(
                        ExportStatus("completed", "/data/exports/e1", 99), tmp_path
                    ),
                    "failed": status(
                        ExportStatus("failed", error_code="conversion_failed", error_detail="no"),
                        tmp_path,
                    ),
                },
            },
        },
    )
