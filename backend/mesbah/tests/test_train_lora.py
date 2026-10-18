from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

pytest.importorskip("torch")
pytest.importorskip("transformers")
pytest.importorskip("peft")
pytest.importorskip("trl")

import torch  # noqa: E402

from mesbah.train import lora  # noqa: E402
from mesbah.train.contract import (  # noqa: E402
    BaseModelRef,
    EventWriter,
    ExampleSource,
    Hyperparams,
    JsonObject,
    Status,
    TrainConfig,
    read_events,
)
from mesbah.train.data import Conversation, Message, Pair, Prepared, prepare  # noqa: E402
from mesbah.train.deltas import LoraModule, read_adapter  # noqa: E402

if TYPE_CHECKING:
    from torch import Tensor
    from transformers import PreTrainedTokenizerBase

pytestmark: pytest.MarkDecorator = pytest.mark.ml

TINY: str = "trl-internal-testing/tiny-Qwen3ForCausalLM"
ROWS: tuple[JsonObject, ...] = (
    {
        "messages": [
            {"role": "user", "content": "What is the capital of Oman?"},
            {"role": "assistant", "content": "Muscat."},
        ]
    },
    {
        "messages": [
            {"role": "user", "content": "Add 2 and 3."},
            {"role": "assistant", "content": "5", "thinking": "Two plus three is five."},
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "Answer briefly."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!", "thinking": "A greeting."},
            {"role": "user", "content": "Goodbye"},
            {"role": "assistant", "content": "Bye."},
        ]
    },
    {"text": "Muscat is the capital of Oman."},
)


@dataclass(frozen=True)
class Run:
    config: TrainConfig
    status: Status


@pytest.fixture(scope="module")
def tiny_model() -> Path:
    from huggingface_hub import snapshot_download

    problem: str = ""
    for local_only in (True, False):
        try:
            return Path(snapshot_download(TINY, local_files_only=local_only))
        except Exception as exc:  # noqa: BLE001 - not cached, or offline
            problem = str(exc)
    pytest.skip(f"{TINY} is not available: {problem}")


@pytest.fixture(scope="module", autouse=True)
def cpu_only() -> Iterator[None]:
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("CUDA_VISIBLE_DEVICES", "")
        patch.setenv("CUDA_DEVICE_ORDER", "PCI_BUS_ID")
        yield


def make_config(
    root: Path,
    model: Path,
    rank: int,
    parent: Path | None = None,
    max_steps: int = 2,
    max_seq_len: int = 512,
) -> TrainConfig:
    root.mkdir(parents=True, exist_ok=True)
    examples: Path = root / "examples.jsonl"
    lines: list[str] = [json.dumps(row) for row in ROWS]
    examples.write_text("\n".join([*lines, "{broken"]) + "\n", encoding="utf-8")
    return TrainConfig(
        run_id=root.name,
        base=BaseModelRef(repo_id=TINY, path=str(model)),
        output_dir=str(root / "adapter"),
        events_path=str(root / "events.jsonl"),
        status_path=str(root / "status.json"),
        cancel_path=str(root / "cancel"),
        examples=(ExampleSource(path=str(examples)),),
        parent_adapter=None if parent is None else str(parent),
        hyperparams=Hyperparams(
            max_steps=max_steps,
            lora_rank=rank,
            lora_alpha=2 * rank,
            learning_rate=1e-3,
            grad_accum=1,
            max_seq_len=max_seq_len,
            quantize_4bit=True,
        ),
    )


@pytest.fixture(scope="module")
def first_run(tmp_path_factory: pytest.TempPathFactory, tiny_model: Path) -> Run:
    config: TrainConfig = make_config(tmp_path_factory.mktemp("first"), tiny_model, rank=4)
    return Run(config=config, status=lora.run(config))


@pytest.fixture(scope="module")
def tokenizer(tiny_model: Path) -> PreTrainedTokenizerBase:
    from transformers import AutoTokenizer

    loaded: PreTrainedTokenizerBase = AutoTokenizer.from_pretrained(str(tiny_model))
    return loaded


def dense(module: LoraModule) -> Tensor:
    return module.scale * (module.b @ module.a)


def test_a_run_on_cpu_saves_a_small_adapter(first_run: Run, tiny_model: Path) -> None:
    status: Status = first_run.status
    adapter: Path = Path(first_run.config.output_dir)
    events: list[JsonObject] = read_events(Path(first_run.config.events_path))
    names: list[object] = [event["event"] for event in events]
    logs: list[JsonObject] = [event for event in events if event["event"] == "log"]

    assert status.status == "completed", status.error
    assert (adapter / "adapter_model.safetensors").is_file()
    assert (adapter / "adapter_config.json").is_file()
    assert status.size_bytes < (tiny_model / "model.safetensors").stat().st_size / 10
    assert names[0] == "loading"
    assert names[-1] == "done"
    assert "begin" in names
    assert len(logs) == 2
    assert all(isinstance(event["loss"], float) for event in logs)
    assert status.metrics.steps == 2
    assert status.metrics.examples == 4
    assert status.metrics.skipped == 1
    assert isinstance(status.metrics.final_loss, float)
    assert status.delta is not None
    assert status.delta.rank == 4
    assert status.delta.parameters > 0
    assert status.delta.total_norm > 0
    assert {layer.layer for layer in status.delta.layers} == {0, 1}
    assert status.delta.change_from_parent is None


def test_quantize_4bit_is_ignored_without_cuda(tmp_path: Path, tiny_model: Path) -> None:
    plan: lora.Plan = lora.make_plan(make_config(tmp_path, tiny_model, rank=4), None)

    assert (plan.cuda, plan.quantize, plan.backend) == (False, False, "transformers")


def test_graft_starts_the_larger_adapter_at_the_parent_delta() -> None:
    generator: torch.Generator = torch.Generator().manual_seed(0)
    parent_a: Tensor = torch.randn(3, 10, generator=generator)
    parent_b: Tensor = torch.randn(12, 3, generator=generator)
    new_a: Tensor = torch.randn(7, 10, generator=generator)
    new_b: Tensor = torch.randn(12, 7, generator=generator)

    a, b = lora.graft(parent_a, parent_b, 2.0, new_a, new_b, 0.25)

    torch.testing.assert_close(0.25 * (b @ a), 2.0 * (parent_b @ parent_a))
    torch.testing.assert_close(a[3:], new_a[3:])
    assert bool((b[:, 3:] == 0).all())
    with pytest.raises(ValueError, match="does not fit"):
        lora.graft(new_a, new_b, 1.0, parent_a, parent_b, 1.0)


def test_grafting_the_parent_reproduces_its_delta(
    first_run: Run, tmp_path: Path, tiny_model: Path, tokenizer: PreTrainedTokenizerBase
) -> None:
    parent_dir: Path = Path(first_run.config.output_dir)
    config: TrainConfig = make_config(tmp_path, tiny_model, rank=8, parent=parent_dir)
    plan: lora.Plan = lora.make_plan(config, lora.read_parent(parent_dir))
    loaded: lora.Loaded = lora.load_model(config, plan, 512, tokenizer)

    grafted: int = lora.graft_parent(loaded.model, parent_dir)

    parent: dict[str, LoraModule] = read_adapter(parent_dir)
    layers: dict[str, torch.nn.Module] = dict(loaded.model.named_modules())
    assert plan.rank == 8
    assert grafted == len(parent) > 0
    for name, module in parent.items():
        layer: torch.nn.Module = layers[name]
        a: Tensor = layer.lora_A["default"].weight.detach().double()
        b: Tensor = layer.lora_B["default"].weight.detach().double()
        assert a.shape[0] == 8
        torch.testing.assert_close(
            float(layer.scaling["default"]) * (b @ a), dense(module), atol=1e-6, rtol=1e-5
        )


def test_enhancing_a_version_trains_from_its_adapter(
    first_run: Run, tmp_path: Path, tiny_model: Path
) -> None:
    parent_dir: Path = Path(first_run.config.output_dir)
    config: TrainConfig = make_config(tmp_path, tiny_model, rank=8, parent=parent_dir)

    status: Status = lora.run(config)

    stages: list[object] = [event.get("stage") for event in read_events(Path(config.events_path))]
    assert status.status == "completed", status.error
    assert "parent" in stages
    assert status.delta is not None
    assert status.delta.rank == 8
    assert status.delta.change_from_parent is not None
    assert status.delta.change_from_parent > 0


def test_a_cancel_during_training_stops_without_saving(
    tmp_path: Path, tiny_model: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config: TrainConfig = make_config(tmp_path, tiny_model, rank=4, max_steps=50)
    began: Callable[[EventWriter, int], None] = EventWriter.begin

    def begin_then_cancel(self: EventWriter, total_steps: int) -> None:
        began(self, total_steps)
        Path(config.cancel_path).touch()

    monkeypatch.setattr(EventWriter, "begin", begin_then_cancel)

    status: Status = lora.run(config)

    assert status.status == "cancelled"
    assert status.metrics.steps == 1
    assert not Path(config.output_dir).exists()


def test_out_of_memory_halves_the_sequence_length_down_to_the_floor(
    tmp_path: Path, tiny_model: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config: TrainConfig = make_config(tmp_path, tiny_model, rank=4, max_seq_len=2048)

    def out_of_memory(*args: object) -> None:
        raise RuntimeError("weights could not be converted") from torch.cuda.OutOfMemoryError(
            "CUDA out of memory. Tried to allocate 2.00 GiB"
        )

    monkeypatch.setattr(lora, "_attempt", out_of_memory)

    status: Status = lora.run(config)

    events: list[JsonObject] = read_events(Path(config.events_path))
    retries: list[object] = [e["max_seq_len"] for e in events if e["event"] == "oom_retry"]
    assert retries == [1024, 512, 256]
    assert status.error is not None
    assert status.error.code == "out_of_memory"
    assert events[-1]["event"] == "error"


def test_a_model_that_does_not_load_is_load_failed(
    tmp_path: Path, tiny_model: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config: TrainConfig = make_config(tmp_path, tiny_model, rank=4)

    def broken(*args: object) -> None:
        raise ValueError("broken weights")

    monkeypatch.setattr(lora, "load_model", broken)

    status: Status = lora.run(config)

    assert status.status == "failed"
    assert status.error is not None
    assert (status.error.code, status.error.detail) == ("load_failed", "ValueError: broken weights")


def test_the_thinking_is_rendered_inside_think_before_the_answer(
    tokenizer: PreTrainedTokenizerBase,
) -> None:
    conversation: Conversation = Conversation(
        (Message("user", "Add 2 and 3."), Message("assistant", "5", thinking="Two plus three."))
    )

    prepared: Prepared = prepare((conversation,), tokenizer)

    pair: Pair = prepared.pairs[0]
    full: str = tokenizer.apply_chat_template(
        [
            {"role": "user", "content": "Add 2 and 3."},
            {"role": "assistant", "content": "5", "reasoning_content": "Two plus three."},
        ],
        tokenize=False,
    )
    assert pair.completion.startswith("<think>\nTwo plus three.\n</think>")
    assert pair.completion.endswith("5<|im_end|>")
    assert full.startswith(pair.prompt)
    assert pair.prompt.endswith("<|im_start|>assistant\n")


def test_an_answer_without_thinking_follows_an_empty_think(
    tokenizer: PreTrainedTokenizerBase,
) -> None:
    conversation: Conversation = Conversation(
        (
            Message("system", "Answer briefly."),
            Message("user", "Hello"),
            Message("assistant", "Hi!", thinking="A greeting."),
            Message("user", "Goodbye"),
            Message("assistant", "Bye."),
        )
    )

    prepared: Prepared = prepare((conversation,), tokenizer)

    pair: Pair = prepared.pairs[0]
    assert prepared.skipped == 0
    assert "Answer briefly." in pair.prompt
    assert "Hi!<|im_end|>" in pair.prompt
    assert pair.prompt.endswith("<think>\n\n</think>\n\n")
    assert pair.completion == "Bye.<|im_end|>"
    assert prepared.tokens > 0
