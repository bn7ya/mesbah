from __future__ import annotations

import json
import random
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from mesbah.architect import Design, count, to_hf_config
from mesbah.think import join_thinking
from mesbah.train import scratch
from mesbah.train.__main__ import main
from mesbah.train.contract import (
    Architecture,
    BaseModelRef,
    ContractError,
    EventWriter,
    ExampleSource,
    Hyperparams,
    JsonObject,
    Metrics,
    Pretrain,
    Status,
    TrainConfig,
    read_events,
    write_status,
)
from mesbah.train.data import Conversation, Message, Pair, Rows, load_rows
from mesbah.train.fake import KNOBS, read_safetensors

if TYPE_CHECKING:
    from torch import Tensor
    from torch.nn import Module
    from transformers import PreTrainedTokenizerBase

QWEN: str = "trl-internal-testing/tiny-Qwen3ForCausalLM"
T5_REPO: str = "hf-internal-testing/tiny-random-t5"
DENSE: Design = Design(
    family="dense_decoder",
    layers=2,
    hidden_size=64,
    heads=4,
    kv_heads=2,
    intermediate_size=128,
    vocab_size=256,
    context_length=128,
)
MOE: Design = Design(
    family="moe_decoder",
    layers=2,
    hidden_size=64,
    heads=4,
    kv_heads=2,
    intermediate_size=32,
    vocab_size=256,
    context_length=128,
    experts=4,
    experts_per_token=2,
)
T5: Design = Design(
    family="encoder_decoder",
    encoder_layers=2,
    decoder_layers=2,
    hidden_size=64,
    heads=4,
    intermediate_size=128,
    vocab_size=256,
    context_length=128,
)
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
    {"text": "Muscat is the capital of Oman. It lies between the sea and the mountains."},
    {"text": "A lamp gives light to everyone in the house, and the house keeps the lamp lit."},
    {"text": "The Gulf of Oman opens into the Arabian Sea, and ships pass it every day."},
)
DOCUMENTED: str = """
{"run_id": "run-2", "kind": "pretrain",
 "base": {"repo_id": "mesbah/my-model", "path": null, "revision": null},
 "architecture": "seq2seq",
 "parent_adapter": null,
 "examples": [{"path": "/x.jsonl", "max_rows": null}],
 "output_dir": "/out", "events_path": "/run/events.jsonl",
 "status_path": "/run/status.json", "cancel_path": "/run/cancel",
 "hyperparams": {"epochs": 1, "max_steps": null, "learning_rate": 0.0003, "lora_rank": 16,
   "lora_alpha": 32, "lora_dropout": 0.0, "use_rslora": false, "target_modules": "all-linear",
   "train_biases": false, "max_seq_len": 512, "batch_size": 8, "grad_accum": 4,
   "warmup_ratio": 0.03, "lr_scheduler": "cosine", "seed": 42, "quantize_4bit": false,
   "gradient_checkpointing": true},
 "gpu_indices": [0],
 "model_config": {"model_type": "t5", "d_model": 512, "feed_forward_proj": "gated-gelu"},
 "tokenizer": "google-t5/t5-small",
 "pretrain": {"optim": "adamw_8bit", "weight_decay": 0.01, "noise_density": 0.15,
   "mean_span_length": 3.0}}
"""


@dataclass(frozen=True)
class Run:
    config: TrainConfig
    status: Status


def seeded(seed: int) -> random.Random:
    return random.Random(seed)  # noqa: S311 - reproducible masks, not secrets


def write_examples(root: Path, rows: tuple[JsonObject, ...] = ROWS) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    examples: Path = root / "examples.jsonl"
    lines: list[str] = [json.dumps(row) for row in rows]
    examples.write_text("\n".join([*lines, "{broken"]) + "\n", encoding="utf-8")
    return examples


def make_config(
    root: Path,
    design: Design,
    tokenizer: str,
    max_steps: int = 3,
    max_seq_len: int = 64,
) -> TrainConfig:
    architecture: Architecture = "seq2seq" if design.family == "encoder_decoder" else "causal"
    return TrainConfig(
        run_id=root.name,
        base=BaseModelRef(repo_id=f"mesbah/{root.name}"),
        output_dir=str(root / "model"),
        events_path=str(root / "events.jsonl"),
        status_path=str(root / "status.json"),
        cancel_path=str(root / "cancel"),
        examples=(ExampleSource(path=str(write_examples(root))),),
        hyperparams=Hyperparams(
            max_steps=max_steps, learning_rate=1e-3, grad_accum=1, max_seq_len=max_seq_len
        ),
        kind="pretrain",
        architecture=architecture,
        model_config=to_hf_config(design),
        tokenizer=tokenizer,
    )


def test_the_documented_pretrain_config_parses_and_round_trips(tmp_path: Path) -> None:
    config: TrainConfig = TrainConfig.from_json(json.loads(DOCUMENTED))

    config.write(tmp_path / "config.json")

    assert config.kind == "pretrain"
    assert config.architecture == "seq2seq"
    assert config.pretrain == Pretrain(optim="adamw_8bit", weight_decay=0.01)
    assert config.to_json() == json.loads(DOCUMENTED)
    assert TrainConfig.read(tmp_path / "config.json") == config


def test_a_pretrain_config_takes_the_architect_config_and_default_settings() -> None:
    data: JsonObject = json.loads(DOCUMENTED)
    del data["pretrain"]
    data["model_config"] = to_hf_config(MOE)
    data["architecture"] = "causal"

    config: TrainConfig = TrainConfig.from_json(data)

    assert config.pretrain == Pretrain()
    assert config.model_config == to_hf_config(MOE)


@pytest.mark.parametrize(
    ("changes", "problem"),
    [
        ({"model_config": None}, "model_config"),
        ({"model_config": {"d_model": 64}}, "model_type"),
        ({"model_config": [1]}, "model_config"),
        ({"tokenizer": None}, "tokenizer"),
        ({"tokenizer": ""}, "tokenizer"),
        ({"parent_adapter": "/versions/a"}, "starts from nothing"),
        ({"base": {"repo_id": "org/name", "path": "/snapshot"}}, "starts from nothing"),
        ({"pretrain": {"optim": "sgd"}}, "optim"),
        ({"pretrain": {"noise_density": 1.0}}, "noise_density"),
        ({"pretrain": {"mean_span_length": 0.5}}, "mean_span_length"),
        ({"pretrain": {"weight_decay": -1}}, "weight_decay"),
        ({"kind": "lora", "architecture": "causal"}, "only for a pretrain run"),
    ],
)
def test_a_wrong_pretrain_config_is_a_contract_error(changes: JsonObject, problem: str) -> None:
    data: JsonObject = {**json.loads(DOCUMENTED), **changes}

    with pytest.raises(ContractError, match=problem):
        TrainConfig.from_json(data)


def test_a_lora_run_trains_a_causal_model_only() -> None:
    data: JsonObject = json.loads(DOCUMENTED)
    for key in ("model_config", "tokenizer", "pretrain"):
        del data[key]
    data["kind"] = "lora"

    with pytest.raises(ContractError, match="causal"):
        TrainConfig.from_json(data)


def test_a_status_carries_the_model_folder_and_its_size(tmp_path: Path) -> None:
    pretrained: Status = Status(
        status="completed",
        model_dir="/out",
        size_bytes=4_096,
        parameters=1_000,
        metrics=Metrics(final_loss=2.5, steps=3, examples=5, skipped=1, seconds=1.0),
    )

    write_status(tmp_path / "status.json", pretrained)
    lora: JsonObject = Status.from_json({"status": "completed", "adapter_dir": "/a"}).to_json()

    assert Status.read(tmp_path / "status.json") == pretrained
    assert (lora["model_dir"], lora["parameters"]) == (None, None)


def test_the_fake_trainer_pretrains_a_model_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(KNOBS, raising=False)
    config: TrainConfig = make_config(tmp_path, T5, T5_REPO)
    config.write(tmp_path / "config.json")

    code: int = main(["--config", str(tmp_path / "config.json"), "--fake"])

    status: Status = Status.read(Path(config.status_path))
    names: list[object] = [event["event"] for event in read_events(Path(config.events_path))]
    model: Path = Path(config.output_dir)
    assert code == 0
    assert status.status == "completed"
    assert (status.model_dir, status.adapter_dir, status.delta) == (config.output_dir, None, None)
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
    assert json.loads((model / "config.json").read_text()) == config.model_config
    weights: int = sum(
        len(matrix) * len(matrix[0])
        for matrix in read_safetensors(model / "model.safetensors").values()
    )
    assert status.parameters == weights > 0
    assert status.size_bytes == sum(path.stat().st_size for path in model.iterdir())
    assert status.metrics.examples == len(ROWS)


def test_the_noise_mask_marks_the_density_in_spans_after_kept_text() -> None:
    settings: Pretrain = Pretrain()

    mask: list[bool] = scratch.random_spans_noise_mask(100, settings, seeded(0))
    again: list[bool] = scratch.random_spans_noise_mask(100, settings, seeded(0))

    starts: int = sum(1 for index, noised in enumerate(mask) if noised and not mask[index - 1])
    assert len(mask) == 100
    assert sum(mask) == 15
    assert starts == 5
    assert not mask[0]
    assert mask == again


def test_span_corruption_hides_spans_behind_sentinels_the_target_restores() -> None:
    ids: list[int] = list(range(10, 70))
    sentinels: list[int] = [1000 + index for index in range(10)]
    mask: list[bool] = scratch.random_spans_noise_mask(60, Pretrain(), seeded(3))

    inputs, targets = scratch.corrupt(ids, mask, sentinels, eos=1)

    spans: dict[int, list[int]] = {}
    for token in targets[:-1]:
        if token in sentinels:
            spans[token] = []
        else:
            spans[list(spans)[-1]].append(token)
    restored: list[int] = [part for token in inputs[:-1] for part in spans.get(token, [token])]
    noise, count_of_spans = scratch.noise_spans(60, Pretrain())
    assert restored == ids
    assert inputs[-1] == targets[-1] == 1
    assert len(inputs) == 60 - noise + count_of_spans + 1
    assert targets[0] == sentinels[0]


def test_a_raw_block_is_as_long_as_still_fits_after_corruption() -> None:
    settings: Pretrain = Pretrain()

    length: int = scratch.raw_length(64, settings)

    noise, spans = scratch.noise_spans(length, settings)
    longer_noise, longer_spans = scratch.noise_spans(length + 1, settings)
    assert length - noise + spans + 1 <= 64
    assert length + 1 - longer_noise + longer_spans + 1 > 64
    assert length > 64


def test_a_conversation_becomes_the_prompt_and_the_reply() -> None:
    conversation: Conversation = Conversation(
        (
            Message("system", "Answer briefly."),
            Message("user", "Add 2 and 3."),
            Message("assistant", "5", thinking="Two plus three."),
        )
    )

    pair: Pair = scratch.seq2seq_pair(conversation)

    assert pair.prompt == "System: Answer briefly.\nUser: Add 2 and 3.\nAssistant:"
    assert pair.completion == join_thinking("Two plus three.", "5")


def test_documents_pack_into_blocks_of_the_sequence_length() -> None:
    blocks: list[list[int]] = scratch.pack([[1, 2, 3], [4, 5], [6, 7, 8, 9]], 4)

    assert blocks == [[1, 2, 3, 4], [5, 6, 7, 8], [9]]


def test_a_long_pair_keeps_the_end_of_its_prompt_and_both_eos() -> None:
    corpus: scratch.Corpus = scratch.Corpus(
        documents=(), pairs=((list(range(20)) + [1], list(range(30, 50)) + [1]),), skipped=0
    )

    examples: list[scratch.Example] = scratch.seq2seq_examples(corpus, 8, Pretrain())

    assert examples == [
        scratch.Example(input_ids=[*range(13, 20), 1], labels=[*range(30, 37), 1]),
    ]


@pytest.fixture(scope="module")
def parts() -> None:
    pytest.importorskip("torch")
    pytest.importorskip("transformers")


@pytest.fixture(scope="module", autouse=True)
def cpu_only() -> Iterator[None]:
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("CUDA_VISIBLE_DEVICES", "")
        patch.setenv("CUDA_DEVICE_ORDER", "PCI_BUS_ID")
        yield


def snapshot(repo: str) -> str:
    from huggingface_hub import snapshot_download

    problem: str = ""
    for local_only in (True, False):
        try:
            found: str = snapshot_download(repo, local_files_only=local_only)
            return found
        except Exception as exc:  # noqa: BLE001 - not cached, or offline
            problem = str(exc)
    pytest.skip(f"{repo} is not available: {problem}")


@pytest.fixture(scope="module")
def qwen(parts: None) -> str:
    return snapshot(QWEN)


@pytest.fixture(scope="module")
def t5_tokenizer(parts: None) -> str:
    return snapshot(T5_REPO)


def tokenizer_of(path: str) -> PreTrainedTokenizerBase:
    from transformers import AutoTokenizer

    loaded: PreTrainedTokenizerBase = AutoTokenizer.from_pretrained(path)
    return loaded


def assert_trained(run: Run, design: Design) -> None:
    status: Status = run.status
    events: list[JsonObject] = read_events(Path(run.config.events_path))
    names: list[object] = [event["event"] for event in events]
    logs: list[JsonObject] = [event for event in events if event["event"] == "log"]
    stages: list[object] = [event["stage"] for event in events if event["event"] == "loading"]
    grown: Design = replace(design, vocab_size=len(tokenizer_of(str(run.config.tokenizer))))
    model: Path = Path(run.config.output_dir)
    assert status.status == "completed", status.error
    assert stages == ["data", "tokenizer", "model"]
    assert names[-2:] == ["saving", "done"]
    assert len(logs) == 3
    assert all(isinstance(event["loss"], float) for event in logs)
    assert (status.metrics.steps, status.metrics.examples, status.metrics.skipped) == (3, 5, 1)
    assert (status.model_dir, status.adapter_dir, status.delta) == (str(model), None, None)
    assert status.parameters == count(grown).total
    assert (model / "config.json").is_file()
    assert (model / "model.safetensors").is_file()
    assert (model / "tokenizer_config.json").is_file()
    assert status.size_bytes == sum(path.stat().st_size for path in model.iterdir())


def new_tokens(run: Run) -> int:
    import torch
    from transformers import AutoModelForCausalLM, AutoModelForSeq2SeqLM

    model_dir: str = str(run.config.output_dir)
    seq2seq: bool = run.config.architecture == "seq2seq"
    model: Module = (
        AutoModelForSeq2SeqLM.from_pretrained(model_dir)
        if seq2seq
        else AutoModelForCausalLM.from_pretrained(model_dir)
    )
    tokenizer: PreTrainedTokenizerBase = tokenizer_of(model_dir)
    prompt: dict[str, Tensor] = tokenizer("User: Hello\nAssistant:", return_tensors="pt")
    with torch.no_grad():
        generated: Tensor = model.generate(
            **prompt, max_new_tokens=4, min_new_tokens=4, do_sample=False
        )
    assert sum(parameter.numel() for parameter in model.parameters()) == run.status.parameters
    assert next(model.parameters()).dtype == torch.bfloat16
    # A decoder returns the prompt before the reply; a seq2seq model, the decoder start token.
    already: int = 1 if seq2seq else int(prompt["input_ids"].shape[-1])
    return int(generated.shape[-1]) - already


@pytest.mark.ml
def test_a_dense_decoder_trains_from_nothing(tmp_path: Path, qwen: str) -> None:
    config: TrainConfig = make_config(tmp_path, DENSE, qwen)

    run: Run = Run(config=config, status=scratch.run(config))

    assert_trained(run, DENSE)
    assert new_tokens(run) == 4


@pytest.mark.ml
def test_a_mixture_of_experts_trains_with_its_router_loss(
    tmp_path: Path, qwen: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from transformers.models.qwen3_moe import modeling_qwen3_moe

    balancing: Callable[..., Tensor] = modeling_qwen3_moe.load_balancing_loss_func
    recorded: list[float] = []

    def recording(*args: object, **kwargs: object) -> Tensor:
        loss: Tensor = balancing(*args, **kwargs)
        recorded.append(float(loss.detach()))
        return loss

    monkeypatch.setattr(modeling_qwen3_moe, "load_balancing_loss_func", recording)
    config: TrainConfig = make_config(tmp_path, MOE, qwen)

    run: Run = Run(config=config, status=scratch.run(config))

    assert_trained(run, MOE)
    saved: JsonObject = json.loads((Path(config.output_dir) / "config.json").read_text())
    assert len(recorded) >= 3
    assert all(loss > 0 for loss in recorded)
    assert saved["output_router_logits"] is False
    assert saved["router_aux_loss_coef"] == to_hf_config(MOE)["router_aux_loss_coef"]
    assert new_tokens(run) == 4


@pytest.mark.ml
def test_the_built_mixture_adds_its_router_loss_to_the_loss(tmp_path: Path, qwen: str) -> None:
    import torch

    config: TrainConfig = make_config(tmp_path, MOE, qwen)
    model: Module = scratch.build_model(config, tokenizer_of(qwen))
    ids: Tensor = torch.randint(0, 1_000, (2, 16), generator=torch.Generator().manual_seed(0))
    coefficient: object = to_hf_config(MOE)["router_aux_loss_coef"]
    assert isinstance(coefficient, float)

    with torch.no_grad():
        trained: Tensor = model(input_ids=ids, labels=ids)
        language: Tensor = model(input_ids=ids, labels=ids, output_router_logits=False)

    assert model.config.output_router_logits is True
    torch.testing.assert_close(trained.loss, language.loss + coefficient * trained.aux_loss)
    assert float(trained.aux_loss) > 0


@pytest.mark.ml
def test_a_t5_trains_on_corrupted_spans_and_on_replies(tmp_path: Path, t5_tokenizer: str) -> None:
    config: TrainConfig = make_config(tmp_path, T5, t5_tokenizer)
    config.write(tmp_path / "config.json")

    code: int = main(["--config", str(tmp_path / "config.json")])

    run: Run = Run(config=config, status=Status.read(Path(config.status_path)))
    assert code == 0
    assert_trained(run, T5)
    assert new_tokens(run) == 4


@pytest.mark.ml
def test_the_collator_corrupts_plain_text_and_keeps_pairs(t5_tokenizer: str) -> None:
    tokenizer: PreTrainedTokenizerBase = tokenizer_of(t5_tokenizer)
    sentinels: list[int] = scratch.ensure_sentinels(tokenizer, 4)
    collator: scratch.SpanCorruptionCollator = scratch.SpanCorruptionCollator(
        pad=0, eos=1, sentinels=sentinels, settings=Pretrain(), seed=0
    )

    batch: dict[str, Tensor] = collator(
        [scratch.Example(input_ids=list(range(200, 260))), scratch.Example([5, 6, 1], [7, 1])]
    )

    assert int(batch["labels"][0, 0]) == sentinels[0]
    assert sentinels[0] in batch["input_ids"][0].tolist()
    assert batch["input_ids"][1].tolist()[:3] == [5, 6, 1]
    assert batch["labels"][1].tolist()[:2] == [7, 1]
    assert set(batch["labels"][1].tolist()[2:]) == {scratch.IGNORE_INDEX}
    assert batch["attention_mask"][1].tolist().count(1) == 3


@pytest.mark.ml
def test_missing_sentinels_are_added_to_the_tokenizer(qwen: str) -> None:
    tokenizer: PreTrainedTokenizerBase = tokenizer_of(qwen)
    before: int = len(tokenizer)

    first: list[int] = scratch.ensure_sentinels(tokenizer, 3)
    again: list[int] = scratch.ensure_sentinels(tokenizer, 3)

    assert len(tokenizer) == before + 3
    assert first == again
    assert len(set(first)) == 3
    assert tokenizer.convert_ids_to_tokens(first[0]) == "<extra_id_0>"


@pytest.mark.ml
def test_a_decoder_learns_conversations_in_the_chat_template(tmp_path: Path, qwen: str) -> None:
    tokenizer: PreTrainedTokenizerBase = tokenizer_of(qwen)
    rows: Rows = load_rows((ExampleSource(path=str(write_examples(tmp_path))),))

    corpus: scratch.Corpus = scratch.tokenize(rows.rows, tokenizer, "causal")

    texts: list[str] = [tokenizer.decode(document) for document in corpus.documents]
    assert "<|im_start|>assistant" in texts[0]
    assert "<think>\nTwo plus three is five.\n</think>" in texts[1]
    assert all(document[-1] == tokenizer.eos_token_id for document in corpus.documents)
    assert corpus.tokens == sum(map(len, corpus.documents))


@pytest.mark.ml
def test_a_cancel_during_pretraining_stops_without_saving(
    tmp_path: Path, t5_tokenizer: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    config: TrainConfig = make_config(tmp_path, T5, t5_tokenizer, max_steps=50)
    began: Callable[[EventWriter, int], None] = EventWriter.begin

    def begin_then_cancel(self: EventWriter, total_steps: int) -> None:
        began(self, total_steps)
        Path(config.cancel_path).touch()

    monkeypatch.setattr(EventWriter, "begin", begin_then_cancel)

    status: Status = scratch.run(config)

    assert status.status == "cancelled"
    assert status.metrics.steps == 1
    assert not Path(config.output_dir).exists()


@pytest.mark.ml
def test_a_config_of_the_wrong_architecture_does_not_load(
    tmp_path: Path, t5_tokenizer: str
) -> None:
    config: TrainConfig = replace(
        make_config(tmp_path, T5, t5_tokenizer), model_config=to_hf_config(DENSE)
    )

    status: Status = scratch.run(config)

    assert status.error is not None
    assert status.error.code == "load_failed"
    assert "qwen3" in status.error.detail


@pytest.mark.ml
def test_out_of_memory_halves_the_sequence_length(
    tmp_path: Path, t5_tokenizer: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import torch

    long: Design = replace(T5, context_length=4_096)
    config: TrainConfig = make_config(tmp_path, long, t5_tokenizer, max_seq_len=2_048)

    def out_of_memory(*args: object) -> None:
        raise torch.cuda.OutOfMemoryError("CUDA out of memory. Tried to allocate 2.00 GiB")

    monkeypatch.setattr(scratch, "_attempt", out_of_memory)

    status: Status = scratch.run(config)

    events: list[JsonObject] = read_events(Path(config.events_path))
    retries: list[object] = [e["max_seq_len"] for e in events if e["event"] == "oom_retry"]
    assert retries == [1024, 512, 256]
    assert status.error is not None
    assert status.error.code == "out_of_memory"
