"""The inference engine — loads a base model (4-bit) + optional LoRA adapter and
generates chat replies.

Design notes
------------
* **Lazy imports.** ``torch``/``transformers``/``peft`` are imported only when a
  generation is actually requested, so the FastAPI app boots instantly even on a
  machine where the ML stack is still installing. Missing deps surface as a clean
  ``RuntimeError`` that the router turns into a 503 with guidance.
* **Single resident model.** On a 16 GB card we keep exactly one model resident.
  Switching the active version only swaps the lightweight LoRA adapter; switching
  the base model reloads. ``unload()`` frees all VRAM — the training manager calls
  it before a run so the fine-tune gets the whole GPU.
* **4-bit (NF4) inference** keeps a 14B model near ~9–10 GB, leaving headroom for
  the KV-cache of long contexts.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Iterator, Optional


class ModelRuntimeUnavailable(RuntimeError):
    """Raised when the torch/transformers stack cannot be imported or used."""


@dataclass
class LoadedModel:
    base_id: str
    adapter_path: Optional[str]
    model: Any
    tokenizer: Any


class InferenceEngine:
    """Process-wide singleton guarding the resident model."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._loaded: Optional[LoadedModel] = None
        # When frozen (during a training run) the engine refuses to load so the
        # training subprocess gets the whole GPU. See freeze()/unfreeze().
        self._frozen = False
        # Memoized heavy ML imports (torch + transformers classes). Importing
        # transformers lazily inside a worker thread races with the /api/system
        # poll's `import transformers`, which can make the FIRST load fail with
        # "cannot import name 'AutoModelForCausalLM'". We resolve it once, under a
        # dedicated lock, and pre-warm it at startup (see warm()).
        self._ml: Optional[tuple] = None
        self._import_lock = threading.Lock()

    def _import_ml(self):
        """Import torch + transformers classes exactly once (thread-safe)."""
        if self._ml is not None:
            return self._ml
        with self._import_lock:
            if self._ml is None:
                import torch
                from transformers import (AutoModelForCausalLM, AutoTokenizer,
                                          BitsAndBytesConfig)
                self._ml = (torch, AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig)
        return self._ml

    def warm(self) -> bool:
        """Pre-resolve the ML imports (called at startup). Best-effort."""
        try:
            self._import_ml()
            return True
        except Exception:
            return False

    # ── status ────────────────────────────────────────────────────────────────
    def status(self) -> dict[str, Any]:
        info: dict[str, Any] = {
            "runtime_available": self._runtime_available(),
            "loaded": self._loaded is not None,
            "base_id": self._loaded.base_id if self._loaded else None,
            "adapter_path": self._loaded.adapter_path if self._loaded else None,
        }
        info.update(self._gpu_info())
        return info

    def _runtime_available(self) -> bool:
        # Cheap once warmed; the heavy import is memoized in _import_ml.
        if self._ml is not None:
            return True
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
            return True
        except Exception:
            return False

    @staticmethod
    def _gpu_info() -> dict[str, Any]:
        try:
            import torch
            if not torch.cuda.is_available():
                return {"cuda": False}
            free, total = torch.cuda.mem_get_info()
            return {
                "cuda": True,
                "device": torch.cuda.get_device_name(0),
                "vram_total_gb": round(total / 1e9, 2),
                "vram_free_gb": round(free / 1e9, 2),
                "vram_used_gb": round((total - free) / 1e9, 2),
            }
        except Exception:
            return {"cuda": False}

    # ── freeze (during training) ────────────────────────────────────────────────
    def freeze(self) -> None:
        """Unload and refuse to load until unfrozen — gives training the whole GPU."""
        with self._lock:
            self._frozen = True
            self.unload()

    def unfreeze(self) -> None:
        with self._lock:
            self._frozen = False

    @property
    def frozen(self) -> bool:
        return self._frozen

    # ── load / unload ───────────────────────────────────────────────────────────
    def ensure_loaded(self, base_id: str, adapter_path: Optional[str] = None) -> LoadedModel:
        with self._lock:
            if self._frozen:
                raise ModelRuntimeUnavailable(
                    "Inference is paused while a training run is using the GPU."
                )
            if self._loaded and self._loaded.base_id == base_id:
                if self._loaded.adapter_path != adapter_path:
                    self._swap_adapter(adapter_path)
                return self._loaded
            self.unload()
            try:
                self._loaded = self._load(base_id, adapter_path)
            except BaseException:
                # A failed/partial load can leave tensors on the GPU — free them
                # so VRAM isn't leaked (otherwise the next attempt OOMs).
                self._loaded = None
                self._free_vram()
                raise
            return self._loaded

    def unload(self) -> None:
        with self._lock:
            self._loaded = None
            self._free_vram()

    @staticmethod
    def _free_vram() -> None:
        """Release cached GPU memory. Safe to call even when nothing is tracked
        as loaded — recovers VRAM leaked by a failed/partial load."""
        try:
            import gc

            import torch
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
        except Exception:
            pass

    def _load(self, base_id: str, adapter_path: Optional[str]) -> LoadedModel:
        try:
            torch, AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig = self._import_ml()
        except Exception as exc:  # pragma: no cover - env dependent
            raise ModelRuntimeUnavailable(
                "The model runtime (torch/transformers) is not importable. "
                "Install backend/requirements-ml.txt into your conda env. "
                f"Original error: {exc}"
            ) from exc

        tokenizer = AutoTokenizer.from_pretrained(base_id, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        quant = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
        # Pin the whole 4-bit model on one GPU — "auto" can offload to CPU/disk,
        # which bitsandbytes 4-bit rejects. Single-GPU box → force GPU 0.
        device_map = {"": torch.cuda.current_device()} if torch.cuda.is_available() else "cpu"
        model = AutoModelForCausalLM.from_pretrained(
            base_id,
            quantization_config=quant,
            dtype=torch.bfloat16,
            device_map=device_map,
            attn_implementation="sdpa",
            trust_remote_code=True,
        )
        model.eval()

        if adapter_path:
            from peft import PeftModel
            model = PeftModel.from_pretrained(model, adapter_path)
            model.eval()

        return LoadedModel(base_id=base_id, adapter_path=adapter_path, model=model, tokenizer=tokenizer)

    def _swap_adapter(self, adapter_path: Optional[str]) -> None:
        """Detach the current adapter and attach a new one without reloading base."""
        assert self._loaded is not None
        model = self._loaded.model
        try:
            from peft import PeftModel
            if isinstance(model, PeftModel):
                # unload() returns the bare base model
                base = model.unload() if hasattr(model, "unload") else model.get_base_model()
            else:
                base = model
            if adapter_path:
                model = PeftModel.from_pretrained(base, adapter_path)
                model.eval()
            else:
                model = base
            self._loaded = LoadedModel(self._loaded.base_id, adapter_path, model, self._loaded.tokenizer)
        except Exception:
            # Fall back to a full reload on any adapter-swap hiccup.
            base_id = self._loaded.base_id
            self.unload()
            self._loaded = self._load(base_id, adapter_path)

    # ── generation ──────────────────────────────────────────────────────────────
    def _build_inputs(self, messages: list[dict[str, str]], enable_thinking: Optional[bool] = None):
        assert self._loaded is not None
        tok = self._loaded.tokenizer
        kwargs: dict[str, Any] = {"tokenize": False, "add_generation_prompt": True}
        # Hybrid-reasoning models (e.g. Qwen3) emit <think>…</think> before the
        # answer. Callers that need clean/structured output (the auto-enhance
        # evaluator, etc.) pass enable_thinking=False. Templates that don't accept
        # the kwarg just fall back to their default.
        if enable_thinking is not None:
            try:
                text = tok.apply_chat_template(messages, enable_thinking=enable_thinking, **kwargs)
            except TypeError:
                text = tok.apply_chat_template(messages, **kwargs)
        else:
            text = tok.apply_chat_template(messages, **kwargs)
        return tok(text, return_tensors="pt").to(self._loaded.model.device)

    def generate(self, messages: list[dict[str, str]], **gen_kwargs: Any) -> str:
        import torch
        enable_thinking = gen_kwargs.pop("enable_thinking", None)
        with self._lock:
            assert self._loaded is not None
            inputs = self._build_inputs(messages, enable_thinking)
            with torch.no_grad():
                out = self._loaded.model.generate(**inputs, **self._gen_config(gen_kwargs))
            new_tokens = out[0][inputs["input_ids"].shape[1]:]
            return self._loaded.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

    def stream(self, messages: list[dict[str, str]], **gen_kwargs: Any) -> Iterator[str]:
        """Yield text chunks as they are produced (for SSE/WebSocket chat)."""
        import torch
        from transformers import TextIteratorStreamer
        enable_thinking = gen_kwargs.pop("enable_thinking", None)
        assert self._loaded is not None
        inputs = self._build_inputs(messages, enable_thinking)
        streamer = TextIteratorStreamer(
            self._loaded.tokenizer, skip_prompt=True, skip_special_tokens=True
        )
        kwargs = {**inputs, **self._gen_config(gen_kwargs), "streamer": streamer}
        thread = threading.Thread(target=self._loaded.model.generate, kwargs=kwargs)
        with torch.no_grad():
            thread.start()
            for chunk in streamer:
                if chunk:
                    yield chunk
        thread.join()

    def _gen_config(self, overrides: dict[str, Any]) -> dict[str, Any]:
        from ...core.config import settings
        cfg: dict[str, Any] = {
            "max_new_tokens": settings.infer_max_new_tokens,
            "temperature": settings.infer_temperature,
            "top_p": settings.infer_top_p,
            "do_sample": True,
            "pad_token_id": self._loaded.tokenizer.pad_token_id if self._loaded else None,
        }
        cfg.update({k: v for k, v in overrides.items() if v is not None})
        if cfg.get("temperature", 1) <= 0:
            cfg["do_sample"] = False
            cfg.pop("temperature", None)
            cfg.pop("top_p", None)
        return cfg


# Process-wide singleton.
engine = InferenceEngine()
