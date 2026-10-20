from __future__ import annotations

import contextlib
import gc
import importlib.util
import sys
import threading
from collections.abc import Iterator
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field
from types import ModuleType
from typing import TYPE_CHECKING, Literal, cast

from mesbah.runtime.errors import (
    GenerationFailed,
    InvalidRequest,
    LoadFailed,
    MissingParts,
    NotLoaded,
    UnknownModel,
)
from mesbah.runtime.specs import BASE, AdapterSpec, ChatMessage, ChatRequest, LoadSpec
from mesbah.think import ends_inside

if TYPE_CHECKING:
    from peft import PeftModel
    from torch import Tensor
    from torch import dtype as TorchDtype
    from transformers import PreTrainedModel, PreTrainedTokenizerBase, TextIteratorStreamer

type Model = PreTrainedModel | PeftModel
type FinishReason = Literal["stop", "length"]

GIB: int = 1024**3
HEADROOM_GIB: int = 1
TRAINING_PARTS: tuple[str, ...] = ("torch", "transformers", "peft")
SPEAKERS: dict[str, str] = {"system": "System", "user": "User", "assistant": "Assistant"}


class StopWhenSet:
    def __init__(self, stop: threading.Event) -> None:
        self.stop: threading.Event = stop

    def __call__(self, input_ids: Tensor, scores: Tensor, **_kwargs: object) -> Tensor:
        import torch

        return torch.full(
            (input_ids.shape[0],), self.stop.is_set(), dtype=torch.bool, device=input_ids.device
        )


@dataclass(frozen=True)
class Placement:
    device_map: dict[str, int] | str | None
    max_memory: dict[int, str] | None
    precision: TorchDtype
    device: str
    cuda: bool


def placement(spec: LoadSpec) -> Placement:
    import torch

    if not torch.cuda.is_available():
        return Placement(None, None, torch.float32, "cpu", cuda=False)
    count: int = torch.cuda.device_count()
    indices: tuple[int, ...] = spec.gpu_indices or (0,)
    absent: list[int] = [index for index in indices if index >= count]
    if absent:
        raise InvalidRequest(f"GPU {absent[0]} is not on this machine, which has {count}.")
    precision: TorchDtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    if len(indices) == 1:
        return Placement({"": indices[0]}, None, precision, f"cuda:{indices[0]}", cuda=True)
    budget: dict[int, str] = {}
    for index in indices:
        total: int = int(torch.cuda.get_device_properties(index).total_memory)
        budget[index] = f"{max(1, total // GIB - HEADROOM_GIB)}GiB"
    device: str = "cuda:" + ",".join(str(index) for index in indices)
    return Placement("auto", budget, precision, device, cuda=True)


def plain_prompt(messages: tuple[ChatMessage, ...]) -> str:
    lines: list[str] = [f"{SPEAKERS[message.role]}: {message.content}" for message in messages]
    return "\n".join([*lines, "Assistant:"])


def sampling(request: ChatRequest) -> dict[str, object]:
    if request.temperature is not None and request.temperature <= 0:
        return {"do_sample": False, "temperature": None, "top_p": None, "top_k": None}
    options: dict[str, object] = {}
    if request.temperature is not None:
        options.update(do_sample=True, temperature=request.temperature)
    if request.top_p is not None:
        options["top_p"] = request.top_p
    return options


@dataclass
class Resident:
    spec: LoadSpec
    model: Model
    tokenizer: PreTrainedTokenizerBase
    device: str
    quantized: bool
    eos: frozenset[int]
    adapters: dict[str, str] = field(default_factory=dict)

    @property
    def templated(self) -> bool:
        template: object = getattr(self.tokenizer, "chat_template", None)
        return self.spec.architecture == "causal" and bool(template)

    def render(self, request: ChatRequest) -> str:
        if not self.templated:
            return plain_prompt(request.messages)
        messages: list[dict[str, str]] = [message.for_template() for message in request.messages]
        if request.enable_thinking is not None:
            with contextlib.suppress(TypeError):
                return cast(
                    str,
                    self.tokenizer.apply_chat_template(
                        messages,
                        tokenize=False,
                        add_generation_prompt=True,
                        enable_thinking=request.enable_thinking,
                    ),
                )
        return cast(
            str,
            self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            ),
        )


def _serving(resident: Resident | None, model: str) -> Resident:
    if resident is None:
        raise NotLoaded("No model is loaded.")
    if model != BASE and model not in resident.adapters:
        raise UnknownModel(f"The model `{model}` does not exist.")
    return resident


def _free_memory() -> None:
    gc.collect()
    torch: ModuleType | None = sys.modules.get("torch")
    if torch is not None and torch.cuda.is_available():
        torch.cuda.empty_cache()


def _eos_ids(model: Model, tokenizer: PreTrainedTokenizerBase) -> frozenset[int]:
    found: set[int] = set()
    for value in (model.generation_config.eos_token_id, tokenizer.eos_token_id):
        if isinstance(value, int):
            found.add(value)
        elif isinstance(value, list):
            found.update(item for item in value if isinstance(item, int))
    return frozenset(found)


def _load_base(spec: LoadSpec) -> Resident:
    missing: list[str] = [name for name in TRAINING_PARTS if importlib.util.find_spec(name) is None]
    if missing:
        raise MissingParts(
            f"{', '.join(missing)} not installed; the engine needs the training parts: "
            'pip install "mesbah[train]"'
        )
    from transformers import (
        AutoModelForCausalLM,
        AutoModelForSeq2SeqLM,
        AutoTokenizer,
        BitsAndBytesConfig,
    )

    where: Placement = placement(spec)
    quantized: bool = (
        spec.quantize_4bit and where.cuda and importlib.util.find_spec("bitsandbytes") is not None
    )
    options: dict[str, object] = {"dtype": where.precision}
    if where.device_map is not None:
        options["device_map"] = where.device_map
    if where.max_memory is not None:
        options["max_memory"] = where.max_memory
    if quantized:
        options["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=where.precision,
        )
    model: Model
    try:
        tokenizer: PreTrainedTokenizerBase = AutoTokenizer.from_pretrained(spec.base)
        if spec.architecture == "seq2seq":
            model = AutoModelForSeq2SeqLM.from_pretrained(spec.base, **options)
        else:
            model = AutoModelForCausalLM.from_pretrained(spec.base, **options)
    except Exception as error:
        _free_memory()
        raise LoadFailed(f"{spec.base} did not load: {error}") from error
    model.eval()
    if tokenizer.pad_token is None and tokenizer.eos_token is not None:
        tokenizer.pad_token = tokenizer.eos_token
    return Resident(
        spec=spec,
        model=model,
        tokenizer=tokenizer,
        device=where.device,
        quantized=quantized,
        eos=_eos_ids(model, tokenizer),
    )


def _attach(resident: Resident, adapter: AdapterSpec) -> None:
    from peft import PeftModel

    if resident.adapters.get(adapter.name) == adapter.path:
        return
    model: Model = resident.model
    try:
        if not isinstance(model, PeftModel):
            model = PeftModel.from_pretrained(model, adapter.path, adapter_name=adapter.name)
        elif adapter.name not in resident.adapters:
            model.load_adapter(adapter.path, adapter_name=adapter.name)
        elif len(resident.adapters) == 1:
            # PEFT cannot delete its last adapter, so the only one is replaced on the bare base.
            resident.model = model.unload()
            resident.adapters.clear()
            model = PeftModel.from_pretrained(
                resident.model, adapter.path, adapter_name=adapter.name
            )
        else:
            model.delete_adapter(adapter.name)
            del resident.adapters[adapter.name]
            model.load_adapter(adapter.path, adapter_name=adapter.name)
    except Exception as error:
        raise LoadFailed(
            f"Adapter {adapter.name} did not load from {adapter.path}: {error}"
        ) from error
    model.eval()
    resident.model = model
    resident.adapters[adapter.name] = adapter.path


class Generation(Iterator[str]):
    def __init__(self, engine: Engine, request: ChatRequest, stop: threading.Event) -> None:
        self.request: ChatRequest = request
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.finish_reason: FinishReason = "stop"
        self.opens_thinking: bool = False
        self._engine: Engine = engine
        self._stop: threading.Event = stop
        self._state: Literal["new", "running", "done"] = "new"
        self._streamer: TextIteratorStreamer | None = None
        self._thread: threading.Thread | None = None
        self._output: Tensor | None = None
        self._error: Exception | None = None
        self._skip: int = 0
        self._eos: frozenset[int] = frozenset()

    def begin(self) -> None:
        if self._state != "new":
            return
        held: Resident | None = self._engine._acquire(self._stop)
        try:
            self._start(_serving(held, self.request.model))
        except BaseException:
            self._state = "done"
            self._engine._release()
            raise
        self._state = "running"

    def __next__(self) -> str:
        self.begin()
        streamer: TextIteratorStreamer | None = self._streamer
        if self._state != "running" or streamer is None:
            raise StopIteration
        for piece in streamer:
            if piece:
                return cast(str, piece)
        self._finish()
        raise StopIteration

    def close(self) -> None:
        if self._state == "running":
            self._stop.set()
            with contextlib.suppress(GenerationFailed):
                self._finish()
        self._state = "done"

    def _start(self, resident: Resident) -> None:
        from transformers import StoppingCriteriaList, TextIteratorStreamer

        request: ChatRequest = self.request
        model: Model = resident.model
        if request.model != BASE:
            model.set_adapter(request.model, inference_mode=True)
        prompt: str = resident.render(request)
        self.opens_thinking = resident.templated and ends_inside(prompt)
        inputs: dict[str, Tensor] = dict(
            resident.tokenizer(
                prompt, return_tensors="pt", add_special_tokens=not resident.templated
            ).to(model.device)
        )
        self.prompt_tokens = int(inputs["input_ids"].shape[-1])
        self._skip = 1 if resident.spec.architecture == "seq2seq" else self.prompt_tokens
        self._eos = resident.eos
        self._streamer = TextIteratorStreamer(
            resident.tokenizer, skip_prompt=True, skip_special_tokens=True
        )
        options: dict[str, object] = {
            **inputs,
            **sampling(request),
            "max_new_tokens": request.max_tokens,
            "streamer": self._streamer,
            "stopping_criteria": StoppingCriteriaList([StopWhenSet(self._stop)]),
            "pad_token_id": resident.tokenizer.pad_token_id,
        }
        bare: bool = request.model == BASE and bool(resident.adapters)
        self._thread = threading.Thread(
            target=self._produce, args=(model, options, bare), name="mesbah-generate", daemon=True
        )
        self._thread.start()

    def _produce(self, model: Model, options: dict[str, object], bare: bool) -> None:
        import torch

        try:
            adapters: AbstractContextManager[object] = (
                model.disable_adapter() if bare else nullcontext()
            )
            with torch.inference_mode(), adapters:
                self._output = model.generate(**options)
        except Exception as error:
            self._error = error
            if self._streamer is not None:
                self._streamer.end()

    def _finish(self) -> None:
        if self._thread is not None:
            self._thread.join()
        output: Tensor | None = self._output
        error: Exception | None = self._error
        self._state = "done"
        self._thread = None
        self._streamer = None
        self._output = None
        self._engine._release()
        if error is not None:
            raise GenerationFailed(f"Generation stopped: {error}") from error
        if output is None:
            return
        generated: Tensor = getattr(output, "sequences", output)[0][self._skip :]
        self.completion_tokens = int(generated.shape[-1])
        if (
            self.completion_tokens >= self.request.max_tokens
            and int(generated[-1]) not in self._eos
        ):
            self.finish_reason = "length"


class Engine:
    def __init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()
        self._resident: Resident | None = None
        self._running: threading.Event | None = None

    def load(self, spec: LoadSpec) -> None:
        with self._lock:
            resident: Resident | None = self._resident
            if resident is None or not resident.spec.same_base(spec):
                self._drop()
                resident = _load_base(spec)
                self._resident = resident
            for adapter in spec.adapters:
                _attach(resident, adapter)

    def unload(self) -> None:
        running: threading.Event | None = self._running
        if running is not None:
            running.set()
        with self._lock:
            self._drop()

    def models(self) -> tuple[str, ...]:
        resident: Resident | None = self._resident
        return () if resident is None else (BASE, *list(resident.adapters))

    def status(self) -> dict[str, object]:
        resident: Resident | None = self._resident
        busy: bool = self._lock.locked()
        if resident is None:
            return {"loaded": False, "busy": busy}
        return {
            "loaded": True,
            "busy": busy,
            "base": resident.spec.base,
            "architecture": resident.spec.architecture,
            "quantized": resident.quantized,
            "device": resident.device,
            "adapters": [
                {"name": name, "path": path} for name, path in list(resident.adapters.items())
            ],
        }

    def generate(self, request: ChatRequest, stop: threading.Event) -> Generation:
        _serving(self._resident, request.model)
        return Generation(self, request, stop)

    def _acquire(self, stop: threading.Event) -> Resident | None:
        self._lock.acquire()
        self._running = stop
        return self._resident

    def _release(self) -> None:
        self._running = None
        self._lock.release()

    def _drop(self) -> None:
        if self._resident is not None:
            self._resident = None
            _free_memory()
