from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from mesbah.train.__main__ import main
from mesbah.train.contract import (
    ContractError,
    DeltaStats,
    EventWriter,
    Failure,
    Hyperparams,
    JsonObject,
    LayerDelta,
    Metrics,
    Status,
    TrainConfig,
    read_events,
    write_status,
)
from mesbah.train.fake import KNOBS

DOCUMENTED: str = """
{"run_id": "run-1", "kind": "lora",
 "base": {"repo_id": "org/name", "path": "/local/snapshot", "revision": null},
 "architecture": "causal",
 "parent_adapter": null,
 "examples": [{"path": "/x.jsonl", "max_rows": null}],
 "output_dir": "/out", "events_path": "/run/events.jsonl",
 "status_path": "/run/status.json", "cancel_path": "/run/cancel",
 "hyperparams": {"epochs": 1, "max_steps": null, "learning_rate": 0.0002, "lora_rank": 16,
   "lora_alpha": 32, "lora_dropout": 0.0, "use_rslora": false, "target_modules": "all-linear",
   "train_biases": false, "max_seq_len": 2048, "batch_size": 1, "grad_accum": 8,
   "warmup_ratio": 0.03, "lr_scheduler": "cosine", "seed": 42, "quantize_4bit": true,
   "gradient_checkpointing": true},
 "gpu_indices": [0]}
"""

ROWS: tuple[JsonObject, ...] = (
    {"messages": [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]},
    {
        "messages": [
            {"role": "user", "content": "2 + 3?"},
            {"role": "assistant", "content": "5", "thinking": "two plus three"},
        ]
    },
    {"text": "a plain paragraph"},
)


def make_config(
    tmp_path: Path,
    rows: tuple[JsonObject, ...] = ROWS,
    parent: Path | None = None,
    rank: int = 4,
) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    examples: Path = tmp_path / "examples.jsonl"
    lines: list[str] = [json.dumps(row) for row in rows]
    examples.write_text("\n".join([*lines, "{not json"]) + "\n", encoding="utf-8")
    run: Path = tmp_path / "run"
    config: TrainConfig = TrainConfig.from_json(
        {
            "run_id": "run-1",
            "base": {"repo_id": "org/name"},
            "parent_adapter": None if parent is None else str(parent),
            "examples": [{"path": str(examples), "max_rows": None}],
            "output_dir": str(tmp_path / "adapter"),
            "events_path": str(run / "events.jsonl"),
            "status_path": str(run / "status.json"),
            "cancel_path": str(run / "cancel"),
            "hyperparams": {"max_steps": 3, "lora_rank": rank, "lora_alpha": 8},
        }
    )
    path: Path = run / "config.json"
    config.write(path)
    return path


def test_the_documented_config_parses_and_round_trips() -> None:
    config: TrainConfig = TrainConfig.from_json(json.loads(DOCUMENTED))

    assert config.base.source == "/local/snapshot"
    assert config.hyperparams == Hyperparams()
    assert config.gpu_indices == (0,)
    assert TrainConfig.from_json(json.loads(json.dumps(config.to_json()))) == config
    assert config.to_json() == json.loads(DOCUMENTED)


def test_a_config_written_to_disk_reads_back_equal(tmp_path: Path) -> None:
    config: TrainConfig = TrainConfig.from_json(json.loads(DOCUMENTED))

    config.write(tmp_path / "config.json")

    assert TrainConfig.read(tmp_path / "config.json") == config


def test_target_modules_may_be_a_list() -> None:
    data: JsonObject = json.loads(DOCUMENTED)
    hyperparams: object = data["hyperparams"]
    assert isinstance(hyperparams, dict)
    hyperparams["target_modules"] = ["q_proj", "v_proj"]

    config: TrainConfig = TrainConfig.from_json(data)

    assert config.hyperparams.target_modules == ("q_proj", "v_proj")
    assert config.to_json() == data


@pytest.mark.parametrize(
    ("key", "value"),
    [("lora_rank", "16"), ("lora_rank", 0), ("warmup_ratio", 1.0), ("use_rslora", 1)],
)
def test_a_wrong_hyperparameter_is_a_contract_error(key: str, value: object) -> None:
    data: JsonObject = json.loads(DOCUMENTED)
    hyperparams: object = data["hyperparams"]
    assert isinstance(hyperparams, dict)
    hyperparams[key] = value

    with pytest.raises(ContractError, match=key):
        TrainConfig.from_json(data)


def test_a_missing_path_is_a_contract_error() -> None:
    data: JsonObject = json.loads(DOCUMENTED)
    del data["status_path"]

    with pytest.raises(ContractError, match="status_path"):
        TrainConfig.from_json(data)


def test_a_status_round_trips(tmp_path: Path) -> None:
    status: Status = Status(
        status="completed",
        adapter_dir="/out",
        size_bytes=1234,
        delta=DeltaStats(
            layers=(LayerDelta(name="model.layers.0.q_proj", layer=0, module="q_proj", norm=0.5),),
            total_norm=0.5,
            parameters=64,
            rank=4,
            change_from_parent=None,
        ),
        metrics=Metrics(final_loss=1.25, steps=3, examples=2, skipped=1, seconds=0.5),
    )

    write_status(tmp_path / "status.json", status)

    assert Status.read(tmp_path / "status.json") == status
    assert not (tmp_path / ".status.json.partial").exists()


def test_a_loss_that_is_not_finite_is_written_as_null(tmp_path: Path) -> None:
    events: EventWriter = EventWriter(tmp_path / "events.jsonl")

    events.log(
        step=1, total_steps=2, epoch=0.5, loss=float("nan"), learning_rate=1e-4, grad_norm=None
    )

    assert read_events(tmp_path / "events.jsonl")[0]["loss"] is None


def test_the_event_writer_appends_one_line_per_event(tmp_path: Path) -> None:
    path: Path = tmp_path / "nested" / "events.jsonl"
    EventWriter(path).loading("data")
    EventWriter(path).error("no_examples", "nothing to learn")

    lines: list[str] = path.read_text(encoding="utf-8").splitlines()
    events: list[JsonObject] = read_events(path)

    assert len(lines) == 2
    assert [event["event"] for event in events] == ["loading", "error"]
    assert events[0]["stage"] == "data"
    assert events[1] == {**events[1], "code": "no_examples", "detail": "nothing to learn"}
    assert all(isinstance(event["ts"], float) for event in events)


def test_the_fake_trainer_completes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(KNOBS, raising=False)
    config_path: Path = make_config(tmp_path)

    code: int = main(["--config", str(config_path), "--fake"])

    config: TrainConfig = TrainConfig.read(config_path)
    status: Status = Status.read(Path(config.status_path))
    events: list[JsonObject] = read_events(Path(config.events_path))
    names: list[object] = [event["event"] for event in events]
    assert code == 0
    assert status.status == "completed"
    assert names == [
        "loading",
        "loading",
        "data",
        "loading",
        "begin",
        "log",
        "log",
        "log",
        "saving",
        "done",
    ]
    assert [event.get("stage") for event in events[:4]] == ["data", "tokenizer", None, "model"]
    assert events[2] == {**events[2], "examples": 3, "skipped": 1}
    losses: list[float] = [float(str(event["loss"])) for event in events if event["event"] == "log"]
    assert losses == sorted(losses, reverse=True)
    assert status.metrics.steps == 3
    assert status.metrics.examples == 3
    assert status.metrics.skipped == 1
    assert status.delta is not None
    assert status.delta.rank == 4
    assert status.delta.total_norm > 0
    assert status.delta.change_from_parent is None
    assert status.adapter_dir == config.output_dir
    adapter: Path = Path(config.output_dir)
    assert status.size_bytes == sum(path.stat().st_size for path in adapter.iterdir())
    assert json.loads((adapter / "adapter_config.json").read_text())["r"] == 4


def test_the_fake_adapter_is_valid_safetensors(tmp_path: Path) -> None:
    config_path: Path = make_config(tmp_path)
    main(["--config", str(config_path), "--fake"])

    raw: bytes = (
        Path(TrainConfig.read(config_path).output_dir) / "adapter_model.safetensors"
    ).read_bytes()
    (length,) = struct.unpack("<Q", raw[:8])
    header: JsonObject = json.loads(raw[8 : 8 + length])

    assert length % 8 == 0
    tensors: dict[str, object] = {
        name: entry for name, entry in header.items() if name != "__metadata__"
    }
    assert len(tensors) == 8
    end: int = 0
    for entry in tensors.values():
        assert isinstance(entry, dict)
        assert entry["dtype"] == "F32"
        rows, columns = entry["shape"]
        start, stop = entry["data_offsets"]
        assert stop - start == rows * columns * 4
        end = max(end, stop)
    assert len(raw) == 8 + length + end


def test_an_enhanced_fake_run_measures_the_change_from_its_parent(tmp_path: Path) -> None:
    parent_path: Path = make_config(tmp_path / "parent")
    main(["--config", str(parent_path), "--fake"])
    parent: Path = Path(TrainConfig.read(parent_path).output_dir)

    same_path: Path = make_config(tmp_path / "same", parent=parent)
    main(["--config", str(same_path), "--fake"])
    larger_path: Path = make_config(tmp_path / "larger", parent=parent, rank=8)
    main(["--config", str(larger_path), "--fake"])

    same: Status = Status.read(Path(TrainConfig.read(same_path).status_path))
    larger: Status = Status.read(Path(TrainConfig.read(larger_path).status_path))
    assert same.delta is not None
    assert larger.delta is not None
    assert same.delta.change_from_parent == pytest.approx(0.0, abs=1e-6)
    assert larger.delta.change_from_parent is not None
    assert larger.delta.change_from_parent > 0


def test_a_cancel_file_cancels_the_run(tmp_path: Path) -> None:
    config_path: Path = make_config(tmp_path)
    config: TrainConfig = TrainConfig.read(config_path)
    Path(config.cancel_path).touch()

    code: int = main(["--config", str(config_path), "--fake"])

    status: Status = Status.read(Path(config.status_path))
    assert code == 0
    assert status.status == "cancelled"
    assert status.adapter_dir is None
    assert not Path(config.output_dir).exists()
    assert "done" not in [event["event"] for event in read_events(Path(config.events_path))]


def test_the_fail_knob_fails_the_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(KNOBS, "fail")
    config_path: Path = make_config(tmp_path)

    code: int = main(["--config", str(config_path), "--fake"])

    config: TrainConfig = TrainConfig.read(config_path)
    status: Status = Status.read(Path(config.status_path))
    last: JsonObject = read_events(Path(config.events_path))[-1]
    assert code == 1
    assert status.status == "failed"
    assert status.error == Failure(code="failed", detail="fake trainer: failed on purpose")
    assert last == {**last, "event": "error", "code": "failed"}
    assert not Path(config.output_dir).exists()


def test_the_oom_knob_reports_out_of_memory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(KNOBS, "oom")
    config_path: Path = make_config(tmp_path)

    code: int = main(["--config", str(config_path), "--fake"])

    config: TrainConfig = TrainConfig.read(config_path)
    status: Status = Status.read(Path(config.status_path))
    names: list[object] = [event["event"] for event in read_events(Path(config.events_path))]
    assert code == 1
    assert status.error is not None
    assert status.error.code == "out_of_memory"
    assert names[-2:] == ["oom_retry", "error"]


def test_no_usable_example_is_no_examples(tmp_path: Path) -> None:
    config_path: Path = make_config(tmp_path, rows=({"messages": []},))

    code: int = main(["--config", str(config_path), "--fake"])

    status: Status = Status.read(Path(TrainConfig.read(config_path).status_path))
    assert code == 1
    assert status.error is not None
    assert status.error.code == "no_examples"
    assert status.metrics.skipped == 2


def test_an_invalid_config_still_reports_a_failed_status(tmp_path: Path) -> None:
    config_path: Path = tmp_path / "config.json"
    status_path: Path = tmp_path / "status.json"
    config_path.write_text(json.dumps({"status_path": str(status_path)}), encoding="utf-8")

    code: int = main(["--config", str(config_path), "--fake"])

    status: Status = Status.read(status_path)
    assert code == 1
    assert status.status == "failed"
    assert status.error is not None
    assert "run_id" in status.error.detail
