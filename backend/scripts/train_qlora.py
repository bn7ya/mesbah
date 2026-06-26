#!/usr/bin/env python
"""Standalone QLoRA fine-tuning subprocess.

Launched by ``app.features.training.manager`` as::

    python scripts/train_qlora.py --config runs/<id>/config.json

It is intentionally **app-independent** (imports nothing from ``app``) so it can
run in any environment that has the ML stack installed, and so the API process
never shares a CUDA context with the trainer.

Contract (see manager.py):
  * reads ``config.json``
  * appends one JSON line per log step to ``metrics_path``
  * writes a terminal ``status_path`` ({status, adapter_path, metrics, error})

Stack (RTX 5080 / Blackwell sm_120 — see docs/MODEL_SELECTION.md):
  * Prefers **Unsloth** (custom Triton kernels; flash-attn has no sm_120 build).
  * Falls back to pure **transformers + peft + trl + bitsandbytes** with
    ``attn_implementation="sdpa"``.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any


def _disable_httpx_brotli() -> None:
    """Avoid the huggingface_hub 1.x httpx/brotli download crash (see
    ``app/core/hf_http.py``): advertise only gzip/deflate so the Hub never serves
    a brotli body to httpx's buggy decoder. Fully guarded; no-op on older hub."""
    try:
        import httpx
        from huggingface_hub.utils import _http as hf_http
    except Exception:
        return
    if not hasattr(hf_http, "set_client_factory"):
        return

    def _factory():
        hooks = []
        base = getattr(hf_http, "hf_request_event_hook", None)
        if base is not None:
            hooks.append(base)

        def _no_brotli(request):
            request.headers["accept-encoding"] = "gzip, deflate"
        hooks.append(_no_brotli)
        return httpx.Client(event_hooks={"request": hooks},
                            follow_redirects=True, timeout=None)

    try:
        hf_http.set_client_factory(_factory)
    except Exception:
        pass


# ── config / io helpers ───────────────────────────────────────────────────────
def load_config(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_status(cfg: dict[str, Any], **fields: Any) -> None:
    Path(cfg["status_path"]).write_text(json.dumps(fields, ensure_ascii=False, indent=2))


class MetricsWriter:
    """Appends metric points to ``metrics.jsonl`` (one JSON object per line)."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # truncate so a re-run starts clean
        self.path.write_text("")

    def emit(self, payload: dict[str, Any]) -> None:
        payload = {"ts": time.time(), **payload}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def gpu_mem() -> dict[str, float]:
    try:
        import torch
        if torch.cuda.is_available():
            return {
                "vram_reserved_gb": round(torch.cuda.memory_reserved() / 1e9, 2),
                "vram_allocated_gb": round(torch.cuda.memory_allocated() / 1e9, 2),
            }
    except Exception:
        pass
    return {}


# ── data ──────────────────────────────────────────────────────────────────────
def load_dataset(cfg: dict[str, Any]):
    from datasets import load_dataset as hf_load
    ds = hf_load("json", data_files=cfg["dataset_path"], split="train")
    return ds


# ── model loading: Unsloth (preferred) ────────────────────────────────────────
def try_load_unsloth(cfg: dict[str, Any]):
    """Return (model, tokenizer) via Unsloth, or None if unavailable/unsuitable."""
    # Resuming an existing adapter is handled more reliably on the HF path.
    if cfg.get("resume_adapter_path"):
        return None
    try:
        from unsloth import FastLanguageModel
    except Exception:
        return None

    try:
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=cfg["base_model"],
            max_seq_length=int(cfg.get("max_seq_len", 4096)),
            dtype=None,                      # auto (bf16 on Blackwell)
            load_in_4bit=bool(cfg.get("load_in_4bit", True)),
        )
    except Exception as exc:
        # If Unsloth can't even load (e.g. VRAM too small for the model), fall
        # back to the HF path which can spill weights to CPU RAM / disk.
        import gc

        import torch
        print(f"[train_qlora] Unsloth load failed ({exc}); using HF offload path.", flush=True)
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return None
    model = FastLanguageModel.get_peft_model(
        model,
        r=int(cfg.get("lora_r", 16)),
        target_modules=cfg.get("target_modules"),
        lora_alpha=int(cfg.get("lora_alpha", 32)),
        lora_dropout=float(cfg.get("lora_dropout", 0.0)),
        bias="none",
        use_gradient_checkpointing="unsloth",   # async activation offload → long ctx
        random_state=int(cfg.get("seed", 42)),
        use_rslora=bool(cfg.get("use_rslora", False)),
    )
    return model, tokenizer


def load_with_offload_fallback(cfg: dict[str, Any], load_fn):
    """Load the 4-bit model on the GPU; if VRAM is exhausted, spill to CPU RAM
    then disk.

    Tier 1 (fast): the whole model on GPU 0 (device_map={"":0}).
    Tier 2 (fallback on CUDA OOM): device_map="auto" with a per-device
      ``max_memory`` cap — GPU first, then CPU RAM (``cpu_offload_gb``), then a
      disk ``offload_folder``. Slower, but lets an over-large model still train.
    """
    import gc
    from pathlib import Path as _Path

    import torch

    if not torch.cuda.is_available():
        return load_fn(None)

    dev = torch.cuda.current_device()
    try:
        return load_fn({"": dev})
    except (torch.cuda.OutOfMemoryError, RuntimeError, ValueError) as exc:
        msg = str(exc).lower()
        if "out of memory" not in msg and "dispatched" not in msg and "memory" not in msg:
            raise
        gc.collect()
        torch.cuda.empty_cache()
        total = torch.cuda.get_device_properties(dev).total_memory
        gpu_gib = max(1, int(total / (1024 ** 3)) - 1)          # leave ~1 GiB headroom
        cpu_gib = int(cfg.get("cpu_offload_gb", 96))
        offload_dir = cfg.get("offload_folder") or "offload"
        _Path(offload_dir).mkdir(parents=True, exist_ok=True)
        print(f"[train_qlora] VRAM full → offload fallback: GPU {gpu_gib}GiB + "
              f"CPU {cpu_gib}GiB + disk {offload_dir} (slower)", flush=True)
        return load_fn(
            "auto",
            max_memory={dev: f"{gpu_gib}GiB", "cpu": f"{cpu_gib}GiB"},
            offload_folder=offload_dir,
            offload_state_dict=True,
        )


# ── model loading: pure HF fallback ───────────────────────────────────────────
def load_hf(cfg: dict[str, Any]):
    import torch
    from peft import LoraConfig, PeftModel, get_peft_model, prepare_model_for_kbit_training
    from transformers import (AutoModelForCausalLM, AutoTokenizer,
                              BitsAndBytesConfig)

    tokenizer = AutoTokenizer.from_pretrained(cfg["base_model"], trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    quant = BitsAndBytesConfig(
        load_in_4bit=bool(cfg.get("load_in_4bit", True)),
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
        # Permit fp32 CPU-offloaded modules (needed by the RAM/disk fallback).
        llm_int8_enable_fp32_cpu_offload=True,
    )
    common = dict(
        quantization_config=quant,
        dtype=torch.bfloat16,                # (torch_dtype is deprecated in transformers 5.x)
        attn_implementation="sdpa",          # Blackwell sm_120: no flash-attn → SDPA
        trust_remote_code=True,
    )

    def _load(device_map, **extra):
        return AutoModelForCausalLM.from_pretrained(cfg["base_model"], device_map=device_map, **common, **extra)

    model = load_with_offload_fallback(cfg, _load)
    model = prepare_model_for_kbit_training(
        model, use_gradient_checkpointing=bool(cfg.get("gradient_checkpointing", True))
    )

    if cfg.get("resume_adapter_path"):
        # "Enhance from node": continue training the parent LoRA adapter.
        model = PeftModel.from_pretrained(model, cfg["resume_adapter_path"], is_trainable=True)
    else:
        lora = LoraConfig(
            r=int(cfg.get("lora_r", 16)),
            lora_alpha=int(cfg.get("lora_alpha", 32)),
            lora_dropout=float(cfg.get("lora_dropout", 0.0)),
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=cfg.get("target_modules"),
        )
        model = get_peft_model(model, lora)
    return model, tokenizer


# ── training ──────────────────────────────────────────────────────────────────
def build_trainer(cfg: dict[str, Any], model, tokenizer, dataset, metrics: MetricsWriter):
    from transformers import TrainerCallback
    from trl import SFTConfig, SFTTrainer

    # Pre-format conversations into a single "text" column via the chat template.
    # vanilla trl auto-handles a "messages" column, but Unsloth's patched trainer
    # requires an explicit text field — doing it here works for both paths.
    if "messages" in dataset.column_names:
        def _fmt(ex):
            return {"text": tokenizer.apply_chat_template(ex["messages"], tokenize=False)}
        dataset = dataset.map(_fmt, remove_columns=dataset.column_names)

    total_steps_holder: dict[str, int] = {"total": int(cfg.get("_total_steps", 0))}

    class LiveCallback(TrainerCallback):
        def on_train_begin(self, args, state, control, **kw):
            total_steps_holder["total"] = state.max_steps or total_steps_holder["total"]
            metrics.emit({"event": "begin", "total_steps": total_steps_holder["total"],
                          **gpu_mem()})

        def on_log(self, args, state, control, logs=None, **kw):
            if not logs:
                return
            metrics.emit({
                "event": "log",
                "step": state.global_step,
                "total_steps": total_steps_holder["total"] or state.max_steps,
                "epoch": round(state.epoch or 0, 3),
                "loss": logs.get("loss"),
                "learning_rate": logs.get("learning_rate"),
                "grad_norm": logs.get("grad_norm"),
                "mean_token_accuracy": logs.get("mean_token_accuracy"),
                **gpu_mem(),
            })

    sft_kwargs: dict[str, Any] = dict(
        output_dir=cfg["output_dir"],
        num_train_epochs=float(cfg.get("epochs", 3)),
        per_device_train_batch_size=int(cfg.get("per_device_batch_size", 1)),
        gradient_accumulation_steps=int(cfg.get("grad_accum_steps", 16)),
        learning_rate=float(cfg.get("learning_rate", 2e-4)),
        lr_scheduler_type=cfg.get("lr_scheduler_type", "cosine"),
        warmup_ratio=float(cfg.get("warmup_ratio", 0.03)),
        weight_decay=float(cfg.get("weight_decay", 0.0)),
        max_length=int(cfg.get("max_seq_len", 4096)),
        bf16=bool(cfg.get("bf16", True)),
        optim=cfg.get("optim", "paged_adamw_8bit"),
        logging_steps=1,
        save_strategy="no",
        report_to=[],
        seed=int(cfg.get("seed", 42)),
        packing=bool(cfg.get("packing", False)),
        gradient_checkpointing=bool(cfg.get("gradient_checkpointing", True)),
    )
    # assistant-only loss + neftune are newer SFTConfig fields; tolerate older trl.
    # assistant_only_loss defaults OFF: it requires the chat template to emit a
    # `{% generation %}` mask, which many templates (e.g. Qwen2.5) lack — enabling
    # it then hard-errors. Training on the full corrected conversation works for
    # every template. Advanced users can opt in via hyperparams.
    optional = {
        "assistant_only_loss": True if cfg.get("assistant_only_loss") else None,
        "neftune_noise_alpha": cfg.get("neftune_noise_alpha"),
        "dataset_text_field": "text",
    }
    args = _make_sftconfig(SFTConfig, sft_kwargs, optional)

    trainer = SFTTrainer(
        model=model,
        args=args,
        train_dataset=dataset,
        processing_class=tokenizer,
        callbacks=[LiveCallback()],
    )
    return trainer


def _make_sftconfig(SFTConfig, base: dict[str, Any], optional: dict[str, Any]):
    """Construct SFTConfig, dropping kwargs an older trl version doesn't accept."""
    kwargs = {**base, **{k: v for k, v in optional.items() if v is not None}}
    while True:
        try:
            return SFTConfig(**kwargs)
        except TypeError as exc:
            msg = str(exc)
            removed = False
            for k in list(optional.keys()):
                if k in kwargs and k in msg:
                    kwargs.pop(k)
                    removed = True
            if not removed:
                raise


# ── OOM handling ──────────────────────────────────────────────────────────────
def _is_oom(exc: BaseException) -> bool:
    """True for a CUDA out-of-memory error (class or message)."""
    try:
        import torch
        if isinstance(exc, torch.cuda.OutOfMemoryError):
            return True
    except Exception:
        pass
    text = str(exc).lower()
    return "out of memory" in text or "cuda oom" in text or "alloc" in text and "memory" in text


def _free_gpu() -> None:
    import gc
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except Exception:
        pass


def _one_attempt(cfg: dict[str, Any], dataset, metrics: MetricsWriter) -> dict[str, Any]:
    """A single load→train→save attempt. Always releases GPU refs (so a retry
    starts from a clean slate). Raises on failure (OOM or otherwise)."""
    model = tokenizer = trainer = None
    try:
        loaded = try_load_unsloth(cfg)
        backend = "unsloth"
        if loaded is None:
            loaded = load_hf(cfg)
            backend = "transformers"
        model, tokenizer = loaded
        metrics.emit({"event": "loaded", "backend": backend, "max_seq_len": int(cfg.get("max_seq_len", 4096)), **gpu_mem()})
        print(f"[train_qlora] model loaded via {backend} @ seq_len={cfg.get('max_seq_len')}", flush=True)

        trainer = build_trainer(cfg, model, tokenizer, dataset, metrics)
        result = trainer.train()

        out = cfg["output_dir"]
        Path(out).mkdir(parents=True, exist_ok=True)
        trainer.model.save_pretrained(out)
        tokenizer.save_pretrained(out)
        return {
            "adapter_path": out,
            "train_loss": float(result.training_loss) if result and result.training_loss else None,
            "backend": backend,
            "max_seq_len": int(cfg.get("max_seq_len", 4096)),
            **gpu_mem(),
        }
    finally:
        # Drop GPU references so the next attempt (or the OOM cleanup) reclaims VRAM.
        del trainer, model, tokenizer
        _free_gpu()


# ── main ──────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    cfg = load_config(ap.parse_args().config)

    _disable_httpx_brotli()   # avoid the httpx/brotli download crash (hub 1.x)

    metrics = MetricsWriter(cfg["metrics_path"])
    print(f"[train_qlora] starting run {cfg.get('run_id')} base={cfg['base_model']}", flush=True)
    write_status(cfg, status="running")

    try:
        dataset = load_dataset(cfg)
        if len(dataset) == 0:
            raise ValueError("Empty dataset — no approved examples to train on.")
        metrics.emit({"event": "dataset", "num_examples": len(dataset)})

        # Auto-OOM recovery: on a CUDA out-of-memory, free VRAM, halve max_seq_len,
        # and retry — down to a floor — so a too-ambitious context self-corrects.
        min_seq = int(cfg.get("min_seq_len", 256))
        max_retries = int(cfg.get("oom_max_retries", 4))
        last_tb = ""
        for attempt in range(max_retries + 1):
            try:
                final_metrics = _one_attempt(cfg, dataset, metrics)
                metrics.emit({"event": "done", **final_metrics})
                write_status(cfg, status="completed",
                             adapter_path=final_metrics["adapter_path"], metrics=final_metrics)
                print("[train_qlora] completed", flush=True)
                return 0
            except BaseException as exc:  # noqa: BLE001
                oom = _is_oom(exc)
                msg = str(exc)[:500]
                last_tb = traceback.format_exc()
            # (exc is dropped here, before cleanup, so VRAM can be reclaimed)
            _free_gpu()
            cur = int(cfg.get("max_seq_len", 4096))
            if oom and cur > min_seq:
                new_len = max(min_seq, cur // 2)
                cfg["max_seq_len"] = new_len
                cfg["packing"] = False  # packing raises peak activation memory
                metrics.emit({"event": "oom_retry", "old_seq_len": cur,
                              "new_seq_len": new_len, "attempt": attempt + 1})
                print(f"[train_qlora] CUDA OOM → retry {attempt + 1} at max_seq_len={new_len}", flush=True)
                continue
            # not an OOM we can recover from → fail
            print(last_tb, file=sys.stderr, flush=True)
            reason = ("CUDA out of memory even at the minimum sequence length; "
                      "use a smaller model or fewer/shorter examples.\n\n" if oom else "") + msg
            metrics.emit({"event": "error", "error": reason})
            write_status(cfg, status="failed", error=f"{reason}\n\n{last_tb}")
            return 1

    except Exception as exc:  # noqa: BLE001 — dataset/setup failures
        tb = traceback.format_exc()
        print(tb, file=sys.stderr, flush=True)
        metrics.emit({"event": "error", "error": str(exc)})
        write_status(cfg, status="failed", error=f"{exc}\n\n{tb}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
