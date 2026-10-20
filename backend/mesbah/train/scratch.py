from __future__ import annotations

import importlib.util
import random
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from mesbah.think import join_thinking
from mesbah.train.contract import (
    Architecture,
    EventWriter,
    Hyperparams,
    JsonValue,
    Pretrain,
    Status,
    TrainConfig,
)
from mesbah.train.data import (
    PLAIN_LABELS,
    Conversation,
    Pair,
    PlainText,
    Prepared,
    Row,
    Rows,
    load_rows,
    prepare,
)
from mesbah.train.deltas import adapter_size_bytes
from mesbah.train.lora import (
    MIN_SEQ_LEN,
    OOM_RETRIES,
    Cancelled,
    Progress,
    TrainingFailure,
    check_cancel,
    describe,
    free_memory,
    guard_load,
    is_oom,
    live_callback,
    run_metrics,
    select_gpus,
    supervise,
)

if TYPE_CHECKING:
    from torch import Tensor
    from transformers import PreTrainedConfig, PreTrainedModel, PreTrainedTokenizerBase, Trainer

type TokenIds = list[int]
type Batch = dict[str, Tensor]

IGNORE_INDEX: int = -100
SENTINEL: str = "<extra_id_{}>"


@dataclass(frozen=True)
class Example:
    input_ids: TokenIds
    labels: TokenIds | None = None


@dataclass(frozen=True)
class Corpus:
    documents: tuple[TokenIds, ...]
    pairs: tuple[tuple[TokenIds, TokenIds], ...]
    skipped: int
    first_rejection: str | None = None

    @property
    def examples(self) -> int:
        return len(self.documents) + len(self.pairs)

    @property
    def tokens(self) -> int:
        return sum(map(len, self.documents)) + sum(len(a) + len(b) for a, b in self.pairs)


def noise_spans(length: int, settings: Pretrain) -> tuple[int, int]:
    noise: int = min(max(round(length * settings.noise_density), 1), length - 1)
    spans: int = max(round(min(noise, length - noise) / settings.mean_span_length), 1)
    return noise, spans


def _segments(items: int, segments: int, rng: random.Random) -> list[int]:
    starts: list[bool] = [index < segments - 1 for index in range(items - 1)]
    rng.shuffle(starts)
    lengths: list[int] = [1]
    for start in starts:
        if start:
            lengths.append(1)
        else:
            lengths[-1] += 1
    return lengths


def random_spans_noise_mask(length: int, settings: Pretrain, rng: random.Random) -> list[bool]:
    noise, spans = noise_spans(length, settings)
    noised: list[int] = _segments(noise, spans, rng)
    kept: list[int] = _segments(length - noise, spans, rng)
    mask: list[bool] = []
    for keep, mark in zip(kept, noised, strict=True):
        mask += [False] * keep + [True] * mark
    return mask


def corrupt(
    ids: Sequence[int], mask: Sequence[bool], sentinels: Sequence[int], eos: int
) -> tuple[TokenIds, TokenIds]:
    inputs: TokenIds = []
    targets: TokenIds = []
    span: int = -1
    previous: bool = False
    for token, noised in zip(ids, mask, strict=True):
        if noised and not previous:
            span += 1
            inputs.append(sentinels[span])
            targets.append(sentinels[span])
        (targets if noised else inputs).append(token)
        previous = noised
    return [*inputs, eos], [*targets, eos]


def _corrupted_length(tokens: int, settings: Pretrain) -> int:
    noise, spans = noise_spans(tokens, settings)
    return tokens - noise + spans + 1


def raw_length(seq_len: int, settings: Pretrain) -> int:
    tokens: int = 2
    while _corrupted_length(tokens + 1, settings) <= seq_len:
        tokens += 1
    return tokens


def ensure_sentinels(tokenizer: PreTrainedTokenizerBase, count: int) -> list[int]:
    names: list[str] = [SENTINEL.format(index) for index in range(count)]
    known: dict[str, int] = tokenizer.get_vocab()
    missing: list[str] = [name for name in names if name not in known]
    if missing:
        tokenizer.add_tokens(missing, special_tokens=True)
    return [int(tokenizer.convert_tokens_to_ids(name)) for name in names]


def seq2seq_pair(conversation: Conversation) -> Pair:
    *prior, target = conversation.messages
    lines: list[str] = [f"{PLAIN_LABELS[message.role]}: {message.content}" for message in prior]
    return Pair(
        prompt="\n".join([*lines, f"{PLAIN_LABELS['assistant']}:"]),
        completion=join_thinking(target.thinking or "", target.content),
    )


def _ended(ids: TokenIds, eos: int) -> TokenIds:
    return ids if ids and ids[-1] == eos else [*ids, eos]


def tokenize(
    rows: Sequence[Row], tokenizer: PreTrainedTokenizerBase, architecture: Architecture
) -> Corpus:
    eos: int = tokenizer.eos_token_id
    if architecture == "causal":
        prepared: Prepared = prepare(rows, tokenizer)
        documents: list[TokenIds] = [
            _ended(list(tokenizer.encode(pair.prompt + pair.completion)), eos)
            for pair in prepared.pairs
        ]
        return Corpus(
            documents=tuple(documents),
            pairs=(),
            skipped=prepared.skipped,
            first_rejection=prepared.first_rejection,
        )
    texts: list[TokenIds] = []
    pairs: list[tuple[TokenIds, TokenIds]] = []
    for row in rows:
        if isinstance(row, PlainText):
            texts.append(_ended(list(tokenizer.encode(row.text, add_special_tokens=False)), eos))
            continue
        pair: Pair = seq2seq_pair(row)
        source: TokenIds = list(tokenizer.encode(pair.prompt, add_special_tokens=False))
        target: TokenIds = list(tokenizer.encode(pair.completion, add_special_tokens=False))
        pairs.append((_ended(source, eos), _ended(target, eos)))
    return Corpus(documents=tuple(texts), pairs=tuple(pairs), skipped=0)


def pack(documents: Sequence[TokenIds], seq_len: int) -> list[TokenIds]:
    stream: TokenIds = [token for document in documents for token in document]
    return [stream[start : start + seq_len] for start in range(0, len(stream), seq_len)]


def seq2seq_examples(corpus: Corpus, seq_len: int, settings: Pretrain) -> list[Example]:
    # The prompt keeps its end, where the last question is; both sides keep their eos.
    examples: list[Example] = [
        Example(
            input_ids=source[max(0, len(source) - seq_len) :],
            labels=[*target[: seq_len - 1], target[-1]] if len(target) > seq_len else target,
        )
        for source, target in corpus.pairs
    ]
    blocks: list[TokenIds] = pack(corpus.documents, raw_length(seq_len, settings))
    examples += [Example(input_ids=block) for block in blocks if len(block) >= 2]
    return examples


def _padded(rows: Sequence[TokenIds], fill: int) -> list[TokenIds]:
    width: int = max(map(len, rows))
    return [[*row, *[fill] * (width - len(row))] for row in rows]


def _mask(rows: Sequence[TokenIds]) -> list[list[int]]:
    width: int = max(map(len, rows))
    return [[1] * len(row) + [0] * (width - len(row)) for row in rows]


class CausalCollator:
    def __init__(self, pad: int) -> None:
        self.pad: int = pad

    def __call__(self, blocks: Sequence[TokenIds]) -> Batch:
        import torch

        return {
            "input_ids": torch.tensor(_padded(blocks, self.pad)),
            "attention_mask": torch.tensor(_mask(blocks)),
            "labels": torch.tensor(_padded(blocks, IGNORE_INDEX)),
        }


class SpanCorruptionCollator:
    def __init__(
        self, pad: int, eos: int, sentinels: Sequence[int], settings: Pretrain, seed: int
    ) -> None:
        self.pad: int = pad
        self.eos: int = eos
        self.sentinels: tuple[int, ...] = tuple(sentinels)
        self.settings: Pretrain = settings
        self.rng: random.Random = random.Random(seed)  # noqa: S311 - masks, not secrets

    def corrupted(self, example: Example) -> tuple[TokenIds, TokenIds]:
        if example.labels is not None:
            return example.input_ids, example.labels
        ids: TokenIds = example.input_ids
        mask: list[bool] = random_spans_noise_mask(len(ids), self.settings, self.rng)
        return corrupt(ids, mask, self.sentinels, self.eos)

    def __call__(self, examples: Sequence[Example]) -> Batch:
        import torch

        made: list[tuple[TokenIds, TokenIds]] = [self.corrupted(example) for example in examples]
        inputs: list[TokenIds] = [source for source, _ in made]
        targets: list[TokenIds] = [target for _, target in made]
        return {
            "input_ids": torch.tensor(_padded(inputs, self.pad)),
            "attention_mask": torch.tensor(_mask(inputs)),
            "labels": torch.tensor(_padded(targets, IGNORE_INDEX)),
        }


def load_tokenizer(config: TrainConfig) -> PreTrainedTokenizerBase:
    from transformers import AutoTokenizer

    tokenizer: PreTrainedTokenizerBase = AutoTokenizer.from_pretrained(config.tokenizer)
    if tokenizer.eos_token is None:
        raise TrainingFailure("load_failed", f"the tokenizer {config.tokenizer} has no eos token")
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer


def _model_settings(config: TrainConfig) -> dict[str, JsonValue]:
    return dict(config.model_config or {})


def vocabulary(config: TrainConfig, tokenizer: PreTrainedTokenizerBase) -> int:
    designed: JsonValue = _model_settings(config).get("vocab_size")
    size: int = len(tokenizer)
    return max(designed, size) if isinstance(designed, int) else size


def context(config: TrainConfig) -> int:
    limit: JsonValue = _model_settings(config).get("max_position_embeddings")
    wanted: int = config.hyperparams.max_seq_len
    return min(wanted, limit) if isinstance(limit, int) and limit > 0 else wanted


def build_model(config: TrainConfig, tokenizer: PreTrainedTokenizerBase) -> PreTrainedModel:
    from transformers import AutoConfig, AutoModelForCausalLM, AutoModelForSeq2SeqLM, set_seed

    settings: dict[str, JsonValue] = _model_settings(config)
    model_type: str = str(settings.pop("model_type"))
    settings["vocab_size"] = vocabulary(config, tokenizer)
    seq2seq: bool = config.architecture == "seq2seq"
    shape: PreTrainedConfig = AutoConfig.for_model(model_type, **settings)
    if bool(shape.is_encoder_decoder) != seq2seq:
        raise TrainingFailure("load_failed", f"{model_type} is not a {config.architecture} model")
    shape.pad_token_id = tokenizer.pad_token_id
    shape.eos_token_id = tokenizer.eos_token_id
    shape.bos_token_id = tokenizer.bos_token_id
    if seq2seq:
        shape.decoder_start_token_id = tokenizer.pad_token_id
    if hasattr(shape, "output_router_logits"):
        shape.output_router_logits = True
    set_seed(config.hyperparams.seed)
    model: PreTrainedModel = (
        AutoModelForSeq2SeqLM.from_config(shape)
        if seq2seq
        else AutoModelForCausalLM.from_config(shape)
    )
    model.config.use_cache = False
    return model


def optimizer(config: TrainConfig, cuda: bool) -> str:
    if config.pretrain.optim == "adamw_torch":
        return "adamw_torch"
    if not cuda:
        print("[mesbah.train] 8-bit Adam needs CUDA; using AdamW on the CPU", file=sys.stderr)
        return "adamw_torch"
    if importlib.util.find_spec("bitsandbytes") is None:
        raise TrainingFailure("load_failed", "8-bit Adam needs bitsandbytes, which is missing")
    return "adamw_8bit"


def build_trainer(
    config: TrainConfig,
    model: PreTrainedModel,
    items: Sequence[TokenIds] | Sequence[Example],
    collator: CausalCollator | SpanCorruptionCollator,
    events: EventWriter,
    progress: Progress,
) -> Trainer:
    import torch
    from transformers import Trainer, TrainingArguments

    settings: Hyperparams = config.hyperparams
    cuda: bool = bool(config.gpu_indices) and torch.cuda.is_available()
    bf16: bool = cuda and torch.cuda.is_bf16_supported()
    arguments: TrainingArguments = TrainingArguments(
        output_dir=str(Path(config.status_path).parent),
        num_train_epochs=settings.epochs,
        max_steps=settings.max_steps or -1,
        per_device_train_batch_size=settings.batch_size,
        gradient_accumulation_steps=settings.grad_accum,
        learning_rate=settings.learning_rate,
        lr_scheduler_type=settings.lr_scheduler,
        warmup_steps=settings.warmup_ratio,
        weight_decay=config.pretrain.weight_decay,
        optim=optimizer(config, cuda),
        logging_steps=1,
        save_strategy="no",
        report_to=[],
        seed=settings.seed,
        bf16=bf16,
        fp16=cuda and not bf16,
        use_cpu=not cuda,
        gradient_checkpointing=settings.gradient_checkpointing,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        remove_unused_columns=False,
        dataloader_pin_memory=cuda,
        disable_tqdm=True,
    )
    return Trainer(
        model=model,
        args=arguments,
        train_dataset=list(items),
        data_collator=collator,
        callbacks=[live_callback(Path(config.cancel_path), events, progress)],
    )


def save(model: PreTrainedModel, tokenizer: PreTrainedTokenizerBase, output: Path) -> None:
    import torch

    model.config.use_cache = True
    # The router loss only matters while training; generation should not compute it.
    if hasattr(model.config, "output_router_logits"):
        model.config.output_router_logits = False
    output.mkdir(parents=True, exist_ok=True)
    model.to(torch.bfloat16).save_pretrained(str(output))
    tokenizer.save_pretrained(str(output))


def _attempt(
    config: TrainConfig,
    tokenizer: PreTrainedTokenizerBase,
    corpus: Corpus,
    sentinels: Sequence[int],
    seq_len: int,
    events: EventWriter,
    progress: Progress,
) -> int:
    pad: int = tokenizer.pad_token_id
    items: list[TokenIds] | list[Example]
    collator: CausalCollator | SpanCorruptionCollator
    if config.architecture == "causal":
        items = pack(corpus.documents, seq_len)
        collator = CausalCollator(pad)
    else:
        items = seq2seq_examples(corpus, seq_len, config.pretrain)
        collator = SpanCorruptionCollator(
            pad, tokenizer.eos_token_id, sentinels, config.pretrain, config.hyperparams.seed
        )
    if not items:
        raise TrainingFailure("no_examples", "the examples hold no text to learn from")
    events.loading("model")
    model: PreTrainedModel = guard_load(lambda: build_model(config, tokenizer))
    check_cancel(config, progress)
    trainer: Trainer = guard_load(
        lambda: build_trainer(config, model, items, collator, events, progress)
    )
    check_cancel(config, progress)
    trainer.train()
    progress.steps = int(trainer.state.global_step)
    if progress.cancelled:
        raise Cancelled
    events.saving()
    save(model, tokenizer, Path(config.output_dir))
    return sum(int(parameter.numel()) for parameter in model.parameters())


def _train(config: TrainConfig, events: EventWriter, progress: Progress, started: float) -> Status:
    # One process trains on one card; several would need one process per card (DDP).
    select_gpus(config.gpu_indices[:1])
    check_cancel(config, progress)
    events.loading("data")
    rows: Rows = load_rows(config.examples)
    progress.skipped = rows.skipped
    if not rows.rows:
        raise TrainingFailure("no_examples", "the example files hold no usable row")
    events.loading("tokenizer")
    tokenizer: PreTrainedTokenizerBase = guard_load(lambda: load_tokenizer(config))
    seq_len: int = context(config)
    sentinels: list[int] = []
    if config.architecture == "seq2seq" and any(isinstance(row, PlainText) for row in rows.rows):
        _, spans = noise_spans(raw_length(seq_len, config.pretrain), config.pretrain)
        sentinels = ensure_sentinels(tokenizer, spans)
    corpus: Corpus = tokenize(rows.rows, tokenizer, config.architecture)
    progress.examples = corpus.examples
    progress.skipped += corpus.skipped
    events.data(examples=progress.examples, skipped=progress.skipped, tokens=corpus.tokens)
    if not corpus.examples:
        raise TrainingFailure(
            "no_examples", corpus.first_rejection or "no example could be rendered"
        )
    retries: int = 0
    parameters: int
    while True:
        oom: str | None = None
        try:
            parameters = _attempt(config, tokenizer, corpus, sentinels, seq_len, events, progress)
            break
        except (TrainingFailure, Cancelled):
            raise
        except Exception as exc:
            if not is_oom(exc):
                raise
            oom = describe(exc)
        free_memory()
        if retries >= OOM_RETRIES or seq_len <= MIN_SEQ_LEN:
            raise TrainingFailure("out_of_memory", f"at max_seq_len={seq_len}: {oom}")
        seq_len = max(MIN_SEQ_LEN, seq_len // 2)
        retries += 1
        progress.steps = 0
        progress.final_loss = None
        events.oom_retry(seq_len)
    output: Path = Path(config.output_dir)
    status: Status = Status(
        status="completed",
        model_dir=str(output),
        size_bytes=adapter_size_bytes(output),
        parameters=parameters,
        metrics=run_metrics(progress, started),
    )
    events.done()
    return status


def run(config: TrainConfig) -> Status:
    return supervise(config, _train)
