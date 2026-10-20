from __future__ import annotations

import gc
import importlib
import importlib.util
import json
import os
import sys
import time
import traceback
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Literal, SupportsFloat, cast

from mesbah.train.contract import (
    ALL_LINEAR,
    ErrorCode,
    EventWriter,
    Failure,
    Hyperparams,
    Metrics,
    Status,
    TrainConfig,
    write_status,
)
from mesbah.train.data import Pair, Prepared, Rows, load_rows, prepare
from mesbah.train.deltas import (
    ADAPTER_CONFIG,
    ADAPTER_WEIGHTS,
    LORA_KEY,
    AdapterSettings,
    adapter_size_bytes,
    delta_stats,
    lora_pairs,
    module_scale,
    read_settings,
)

if TYPE_CHECKING:
    from peft import LoraConfig, PeftModel
    from torch import Tensor
    from torch import dtype as DType
    from torch.nn import Module
    from transformers import (
        PreTrainedTokenizerBase,
        TrainerCallback,
        TrainerControl,
        TrainerState,
        TrainingArguments,
    )
    from trl import SFTTrainer

type Backend = Literal["unsloth", "transformers"]
type Targets = str | tuple[str, ...]
type Training = Callable[[TrainConfig, EventWriter, Progress, float], Status]

MIN_SEQ_LEN: int = 256
OOM_RETRIES: int = 4
DETAIL_LIMIT: int = 4000
ADAPTER_NAME: str = "default"
GIB: int = 1024**3
UNSLOTH_TARGETS: tuple[str, ...] = (
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
    "gate_proj",
    "up_proj",
    "down_proj",
)


class TrainingFailure(Exception):
    def __init__(self, code: ErrorCode, detail: str) -> None:
        super().__init__(detail)
        self.code: ErrorCode = code
        self.detail: str = detail


class Cancelled(Exception):
    pass


@dataclass
class Progress:
    examples: int = 0
    skipped: int = 0
    steps: int = 0
    final_loss: float | None = None
    cancelled: bool = False


@dataclass(frozen=True)
class Parent:
    path: Path
    rank: int
    targets: Targets | None


@dataclass(frozen=True)
class Plan:
    backend: Backend
    cuda: bool
    gpus: int
    quantize: bool
    rank: int
    targets: Targets


@dataclass(frozen=True)
class Loaded:
    model: PeftModel
    tokenizer: PreTrainedTokenizerBase
    backend: Backend


def exception_chain(exc: BaseException) -> Iterator[BaseException]:
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def is_oom(exc: BaseException) -> bool:
    loaded: ModuleType | None = sys.modules.get("torch")
    kinds: tuple[type[BaseException], ...] = (
        () if loaded is None else (loaded.cuda.OutOfMemoryError,)
    )
    return any(
        isinstance(link, kinds) or "out of memory" in str(link).lower()
        for link in exception_chain(exc)
    )


def describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"[:DETAIL_LIMIT]


def free_memory() -> None:
    gc.collect()
    loaded: ModuleType | None = sys.modules.get("torch")
    if loaded is not None and loaded.cuda.is_available():
        loaded.cuda.empty_cache()
        loaded.cuda.ipc_collect()


def select_gpus(indices: tuple[int, ...]) -> None:
    # The indices are NVML's, in PCI bus order; CUDA then numbers the chosen cards from 0.
    os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    os.environ["CUDA_VISIBLE_DEVICES"] = ",".join(str(index) for index in indices)


def guard_load[T](load: Callable[[], T]) -> T:
    try:
        return load()
    except TrainingFailure:
        raise
    except Exception as exc:
        code: ErrorCode = "out_of_memory" if is_oom(exc) else "load_failed"
        raise TrainingFailure(code, describe(exc)) from exc


def read_parent(path: Path) -> Parent:
    if not (path / ADAPTER_WEIGHTS).is_file() or not (path / ADAPTER_CONFIG).is_file():
        raise TrainingFailure("load_failed", f"no LoRA adapter in the parent folder {path}")
    parsed: object = json.loads((path / ADAPTER_CONFIG).read_text(encoding="utf-8"))
    found: Mapping[str, object] = (
        cast(Mapping[str, object], parsed) if isinstance(parsed, dict) else {}
    )
    rank: object = found.get("r")
    patterns: object = found.get("rank_pattern") or {}
    if isinstance(rank, bool) or not isinstance(rank, int) or not isinstance(patterns, dict):
        raise TrainingFailure("load_failed", f"the parent adapter in {path} has no rank")
    ranks: list[int] = [
        value
        for value in cast(Mapping[object, object], patterns).values()
        if isinstance(value, int) and not isinstance(value, bool)
    ]
    targets: object = found.get("target_modules")
    parent_targets: Targets | None = None
    if isinstance(targets, str):
        parent_targets = targets
    elif isinstance(targets, list):
        parent_targets = tuple(sorted(str(name) for name in cast(list[object], targets)))
    return Parent(path=path, rank=max([rank, *ranks]), targets=parent_targets)


def merged_targets(requested: Targets, parent: Targets | None) -> Targets:
    if parent is None or requested == ALL_LINEAR:
        return requested
    if parent == ALL_LINEAR:
        return ALL_LINEAR
    if isinstance(requested, tuple) and isinstance(parent, tuple):
        return tuple(sorted(set(requested) | set(parent)))
    return requested


def make_plan(config: TrainConfig, parent: Parent | None) -> Plan:
    import torch

    settings: Hyperparams = config.hyperparams
    cuda: bool = bool(config.gpu_indices) and torch.cuda.is_available()
    gpus: int = int(torch.cuda.device_count()) if cuda else 0
    rank: int = settings.lora_rank if parent is None else max(settings.lora_rank, parent.rank)
    unsloth: bool = (
        cuda
        and gpus == 1
        and not settings.train_biases
        and (parent is None or parent.rank == rank)
        and importlib.util.find_spec("unsloth") is not None
    )
    if unsloth:
        try:
            # Unsloth patches transformers and TRL, so it has to be imported before either.
            importlib.import_module("unsloth")
        except Exception as exc:  # noqa: BLE001 - transformers trains without it
            print(f"[mesbah.train] Unsloth unavailable: {describe(exc)}", file=sys.stderr)
            unsloth = False
    return Plan(
        backend="unsloth" if unsloth else "transformers",
        cuda=cuda,
        gpus=gpus,
        quantize=(
            settings.quantize_4bit and cuda and importlib.util.find_spec("bitsandbytes") is not None
        ),
        rank=rank,
        targets=merged_targets(settings.target_modules, None if parent is None else parent.targets),
    )


def _origin(config: TrainConfig) -> tuple[str, dict[str, str]]:
    if config.base.path:
        return config.base.path, {}
    revision: dict[str, str] = {"revision": config.base.revision} if config.base.revision else {}
    return config.base.repo_id, revision


def compute_dtype(plan: Plan) -> DType:
    import torch

    if not plan.cuda:
        return torch.float32
    return torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16


def load_tokenizer(config: TrainConfig) -> PreTrainedTokenizerBase:
    from transformers import AutoTokenizer

    source, revision = _origin(config)
    tokenizer: PreTrainedTokenizerBase = AutoTokenizer.from_pretrained(source, **revision)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer


def _gpu_budget(gpus: int) -> dict[int, str]:
    import torch

    return {
        index: f"{max(1, int(torch.cuda.get_device_properties(index).total_memory) // GIB - 1)}GiB"
        for index in range(gpus)
    }


def lora_config_for(plan: Plan, settings: Hyperparams) -> LoraConfig:
    from peft import LoraConfig

    return LoraConfig(
        r=plan.rank,
        lora_alpha=settings.lora_alpha,
        lora_dropout=settings.lora_dropout,
        target_modules=plan.targets if isinstance(plan.targets, str) else list(plan.targets),
        use_rslora=settings.use_rslora,
        bias="lora_only" if settings.train_biases else "none",
        task_type="CAUSAL_LM",
    )


def _load_transformers(
    config: TrainConfig, plan: Plan, tokenizer: PreTrainedTokenizerBase
) -> Loaded:
    from peft import get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig

    source, revision = _origin(config)
    dtype: DType = compute_dtype(plan)
    options: dict[str, object] = {"dtype": dtype, **revision}
    if plan.quantize:
        options["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=dtype,
        )
    if plan.cuda and plan.gpus > 1:
        options["device_map"] = "balanced"
        options["max_memory"] = _gpu_budget(plan.gpus)
    elif plan.cuda:
        options["device_map"] = {"": 0}
    model: Module = AutoModelForCausalLM.from_pretrained(source, **options)
    model.config.use_cache = False
    if plan.quantize:
        model = prepare_model_for_kbit_training(
            model,
            use_gradient_checkpointing=config.hyperparams.gradient_checkpointing,
            gradient_checkpointing_kwargs={"use_reentrant": False},
        )
    adapted: PeftModel = get_peft_model(model, lora_config_for(plan, config.hyperparams))
    return Loaded(model=adapted, tokenizer=tokenizer, backend="transformers")


def _load_unsloth(config: TrainConfig, plan: Plan, seq_len: int) -> Loaded:
    from unsloth import FastLanguageModel

    source, revision = _origin(config)
    settings: Hyperparams = config.hyperparams
    targets: str | list[str] = (
        list(plan.targets) if isinstance(plan.targets, tuple) else plan.targets
    )
    if targets == ALL_LINEAR:
        targets = list(UNSLOTH_TARGETS)
    model: Module
    tokenizer: PreTrainedTokenizerBase
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=source,
        max_seq_length=seq_len,
        dtype=None,
        load_in_4bit=plan.quantize,
        **revision,
    )
    adapted: PeftModel = FastLanguageModel.get_peft_model(
        model,
        r=plan.rank,
        target_modules=targets,
        lora_alpha=settings.lora_alpha,
        lora_dropout=settings.lora_dropout,
        bias="none",
        use_gradient_checkpointing="unsloth" if settings.gradient_checkpointing else False,
        random_state=settings.seed,
        use_rslora=settings.use_rslora,
        max_seq_length=seq_len,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    return Loaded(model=adapted, tokenizer=tokenizer, backend="unsloth")


def load_model(
    config: TrainConfig, plan: Plan, seq_len: int, tokenizer: PreTrainedTokenizerBase
) -> Loaded:
    if plan.backend == "unsloth":
        failure: str | None = None
        try:
            return _load_unsloth(config, plan, seq_len)
        except Exception as exc:  # noqa: BLE001 - the transformers path may still load it
            failure = describe(exc)
        free_memory()
        print(f"[mesbah.train] Unsloth failed, using transformers: {failure}", file=sys.stderr)
    return _load_transformers(config, plan, tokenizer)


def graft(
    parent_a: Tensor,
    parent_b: Tensor,
    parent_scale: float,
    new_a: Tensor,
    new_b: Tensor,
    new_scale: float,
) -> tuple[Tensor, Tensor]:
    import torch

    rank: int = int(parent_a.shape[0])
    fits: bool = (
        parent_a.shape[1] == new_a.shape[1]
        and parent_b.shape[0] == new_b.shape[0]
        and parent_b.shape[1] == rank
        and rank <= new_a.shape[0]
    )
    if not fits:
        raise ValueError(
            f"a rank-{rank} delta of shape {tuple(parent_b.shape)}x{tuple(parent_a.shape)} "
            f"does not fit an adapter of shape {tuple(new_b.shape)}x{tuple(new_a.shape)}"
        )
    a: Tensor = new_a.detach().clone()
    a[:rank] = parent_a.to(device=a.device, dtype=a.dtype)
    b: Tensor = torch.zeros_like(new_b)
    b[:, :rank] = (parent_b.double() * (parent_scale / new_scale)).to(
        device=b.device, dtype=b.dtype
    )
    return a, b


def graft_parent(model: PeftModel, parent_dir: Path) -> int:
    import torch
    from safetensors.torch import load_file

    settings: AdapterSettings = read_settings(parent_dir)
    tensors: dict[str, Tensor] = load_file(str(parent_dir / ADAPTER_WEIGHTS))
    layers: dict[str, Module] = dict(model.named_modules())
    parameters: dict[str, Tensor] = dict(model.named_parameters())
    grafted: int = 0
    for name, (parent_a, parent_b) in lora_pairs(tensors).items():
        layer: Module | None = layers.get(name)
        if layer is None or not hasattr(layer, "lora_A"):
            raise ValueError(f"the new adapter does not reach {name}, which the parent changes")
        a_weight: Tensor = layer.lora_A[ADAPTER_NAME].weight
        b_weight: Tensor = layer.lora_B[ADAPTER_NAME].weight
        a, b = graft(
            parent_a,
            parent_b,
            module_scale(settings, name, int(parent_a.shape[0])),
            a_weight,
            b_weight,
            float(layer.scaling[ADAPTER_NAME]),
        )
        with torch.no_grad():
            a_weight.copy_(a)
            b_weight.copy_(b)
        grafted += 1
    for key, tensor in tensors.items():
        if LORA_KEY.match(key):
            continue
        target: Tensor | None = parameters.get(key)
        if target is None:
            target = parameters.get(key.replace(".bias", ".base_layer.bias"))
        if target is None or tuple(target.shape) != tuple(tensor.shape):
            raise ValueError(
                f"the parent adapter holds {key}, which the new adapter has no room for"
            )
        with torch.no_grad():
            target.copy_(tensor.to(device=target.device, dtype=target.dtype))
    return grafted


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, SupportsFloat):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def live_callback(cancel_path: Path, events: EventWriter, progress: Progress) -> TrainerCallback:
    from transformers import TrainerCallback

    class Live(TrainerCallback):  # type: ignore[misc]
        def on_train_begin(
            self,
            args: TrainingArguments,
            state: TrainerState,
            control: TrainerControl,
            **kwargs: object,
        ) -> None:
            events.begin(total_steps=int(state.max_steps))

        def on_log(
            self,
            args: TrainingArguments,
            state: TrainerState,
            control: TrainerControl,
            logs: Mapping[str, object] | None = None,
            **kwargs: object,
        ) -> None:
            if not logs or "loss" not in logs:
                return
            loss: float | None = _number(logs.get("loss"))
            progress.final_loss = progress.final_loss if loss is None else loss
            events.log(
                step=int(state.global_step),
                total_steps=int(state.max_steps),
                epoch=_number(state.epoch),
                loss=loss,
                learning_rate=_number(logs.get("learning_rate")),
                grad_norm=_number(logs.get("grad_norm")),
            )

        def on_step_end(
            self,
            args: TrainingArguments,
            state: TrainerState,
            control: TrainerControl,
            **kwargs: object,
        ) -> None:
            progress.steps = int(state.global_step)
            if cancel_path.exists():
                progress.cancelled = True
                control.should_training_stop = True

    return Live()


def build_trainer(
    config: TrainConfig,
    plan: Plan,
    loaded: Loaded,
    pairs: tuple[Pair, ...],
    seq_len: int,
    events: EventWriter,
    progress: Progress,
) -> SFTTrainer:
    import torch
    from datasets import Dataset
    from trl import SFTConfig, SFTTrainer

    settings: Hyperparams = config.hyperparams
    dtype: DType = compute_dtype(plan)
    arguments: SFTConfig = SFTConfig(
        output_dir=str(Path(config.status_path).parent),
        num_train_epochs=settings.epochs,
        max_steps=settings.max_steps or -1,
        per_device_train_batch_size=settings.batch_size,
        gradient_accumulation_steps=settings.grad_accum,
        learning_rate=settings.learning_rate,
        lr_scheduler_type=settings.lr_scheduler,
        warmup_steps=settings.warmup_ratio,
        max_length=seq_len,
        completion_only_loss=True,
        logging_steps=1,
        save_strategy="no",
        report_to=[],
        seed=settings.seed,
        bf16=plan.cuda and dtype == torch.bfloat16,
        fp16=plan.cuda and dtype == torch.float16,
        use_cpu=not plan.cuda,
        optim="paged_adamw_8bit" if plan.quantize else "adamw_torch",
        gradient_checkpointing=settings.gradient_checkpointing and loaded.backend == "transformers",
        gradient_checkpointing_kwargs={"use_reentrant": False},
        dataloader_pin_memory=plan.cuda,
        disable_tqdm=True,
    )
    dataset: Dataset = Dataset.from_list(
        [{"prompt": pair.prompt, "completion": pair.completion} for pair in pairs]
    )
    return SFTTrainer(
        model=loaded.model,
        args=arguments,
        train_dataset=dataset,
        processing_class=loaded.tokenizer,
        callbacks=[live_callback(Path(config.cancel_path), events, progress)],
    )


def check_cancel(config: TrainConfig, progress: Progress) -> None:
    if progress.cancelled or Path(config.cancel_path).exists():
        progress.cancelled = True
        raise Cancelled


def _attempt(
    config: TrainConfig,
    plan: Plan,
    parent: Parent | None,
    tokenizer: PreTrainedTokenizerBase,
    pairs: tuple[Pair, ...],
    seq_len: int,
    events: EventWriter,
    progress: Progress,
) -> None:
    events.loading("model")
    loaded: Loaded = guard_load(lambda: load_model(config, plan, seq_len, tokenizer))
    if parent is not None:
        events.loading("parent")
        guard_load(lambda: graft_parent(loaded.model, parent.path))
    check_cancel(config, progress)
    trainer: SFTTrainer = build_trainer(config, plan, loaded, pairs, seq_len, events, progress)
    if len(trainer.train_dataset) == 0:
        raise TrainingFailure(
            "no_examples", f"every prompt fills max_seq_len={seq_len} before its answer starts"
        )
    check_cancel(config, progress)
    trainer.train()
    progress.steps = int(trainer.state.global_step)
    if progress.cancelled:
        raise Cancelled
    events.saving()
    output: Path = Path(config.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    trainer.model.save_pretrained(str(output))


def run_metrics(progress: Progress, started: float) -> Metrics:
    return Metrics(
        final_loss=progress.final_loss,
        steps=progress.steps,
        examples=progress.examples,
        skipped=progress.skipped,
        seconds=round(time.monotonic() - started, 3),
    )


def _train(config: TrainConfig, events: EventWriter, progress: Progress, started: float) -> Status:
    select_gpus(config.gpu_indices)
    check_cancel(config, progress)
    events.loading("data")
    rows: Rows = load_rows(config.examples)
    progress.skipped = rows.skipped
    if not rows.rows:
        raise TrainingFailure("no_examples", "the example files hold no usable row")
    parent_dir: str | None = config.parent_adapter
    parent: Parent | None = (
        None if parent_dir is None else guard_load(lambda: read_parent(Path(parent_dir)))
    )
    plan: Plan = guard_load(lambda: make_plan(config, parent))
    events.loading("tokenizer")
    tokenizer: PreTrainedTokenizerBase = guard_load(lambda: load_tokenizer(config))
    prepared: Prepared = prepare(rows.rows, tokenizer)
    progress.examples = len(prepared.pairs)
    progress.skipped += prepared.skipped
    events.data(examples=progress.examples, skipped=progress.skipped, tokens=prepared.tokens)
    if not prepared.pairs:
        raise TrainingFailure(
            "no_examples", prepared.first_rejection or "no example could be rendered"
        )
    seq_len: int = config.hyperparams.max_seq_len
    retries: int = 0
    while True:
        oom: str | None = None
        try:
            _attempt(config, plan, parent, tokenizer, prepared.pairs, seq_len, events, progress)
            break
        except (TrainingFailure, Cancelled):
            raise
        except Exception as exc:
            if not is_oom(exc):
                raise
            oom = describe(exc)
        # Out of the except block, so the traceback no longer holds the model's tensors.
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
        adapter_dir=str(output),
        size_bytes=adapter_size_bytes(output),
        delta=delta_stats(output, None if parent is None else parent.path),
        metrics=run_metrics(progress, started),
    )
    events.done()
    return status


def _failed(
    events: EventWriter, progress: Progress, started: float, code: ErrorCode, detail: str
) -> Status:
    events.error(code, detail)
    return Status(
        status="failed",
        error=Failure(code=code, detail=detail),
        metrics=run_metrics(progress, started),
    )


def supervise(config: TrainConfig, train: Training) -> Status:
    started: float = time.monotonic()
    events: EventWriter = EventWriter(Path(config.events_path))
    progress: Progress = Progress()
    status: Status
    try:
        status = train(config, events, progress, started)
    except TrainingFailure as failure:
        traceback.print_exc()
        status = _failed(events, progress, started, failure.code, failure.detail)
    except (Cancelled, KeyboardInterrupt):
        status = Status(status="cancelled", metrics=run_metrics(progress, started))
    except Exception as exc:  # noqa: BLE001 - every failure ends as a failed status
        traceback.print_exc()
        code: ErrorCode = "out_of_memory" if is_oom(exc) else "failed"
        status = _failed(events, progress, started, code, describe(exc))
    write_status(Path(config.status_path), status)
    return status


def run(config: TrainConfig) -> Status:
    return supervise(config, _train)
