#!/usr/bin/env python
"""Standalone FROM-SCRATCH training subprocess.

Launched by ``app.features.training.manager`` for projects of kind ``scratch``::

    python scripts/train_scratch.py --config runs/<id>/config.json

Like ``train_qlora.py`` it is **app-independent** and obeys the same contract:
reads ``config.json``, appends one JSON line per log step to ``metrics_path``,
writes a terminal ``status_path`` ({status, adapter_path, metrics, error}).

What it does that QLoRA does not:
  * Builds a model from a **custom architecture spec** (``config["architecture"]``)
    via ``AutoConfig`` + ``AutoModelForCausalLM.from_config`` — i.e. RANDOM weights,
    no pretrained download.
  * Embedding layer: either a **new** (random) trainable embedding, or load a
    **pretrained** embedding from another HF repo (adopting its tokenizer/vocab).
    Either way the embedding is trainable (full training trains everything).
  * Trains on an **HF dataset corpus** (``dataset_repo`` / ``text_field``).
  * Optional **paged training**: dispatch the model across GPU→CPU→disk with a
    VRAM budget so a large model still fits memory.

⚠ Honesty: paging fixes *memory*, not *compute*. Training a real-size model from
scratch on one GPU will not converge in any reasonable time. This is an
experimental capability; expect undertrained models.
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
    """Stop huggingface_hub's httpx client from negotiating brotli.

    huggingface_hub 1.x downloads via httpx, whose brotli decoder is buggy and
    raises mid-stream (``DecodingError: brotli: ... can_accept_more_data() is
    False``) on some dataset/model files. Registering a client factory that
    advertises only gzip/deflate makes the Hub serve a non-brotli encoding, so the
    broken decoder is never used. Fully guarded — a no-op on older hub (requests).
    """
    try:
        import httpx
        from huggingface_hub.utils import _http as hf_http
    except Exception:
        return
    if not hasattr(hf_http, "set_client_factory"):
        return

    def _factory() -> "httpx.Client":
        hooks = []
        base = getattr(hf_http, "hf_request_event_hook", None)
        if base is not None:
            hooks.append(base)

        def _no_brotli(request):  # drop 'br' so httpx never invokes brotlicffi
            request.headers["accept-encoding"] = "gzip, deflate"
        hooks.append(_no_brotli)
        return httpx.Client(event_hooks={"request": hooks},
                            follow_redirects=True, timeout=None)

    try:
        hf_http.set_client_factory(_factory)
    except Exception:
        pass


# ── config / io helpers (same contract as train_qlora.py) ──────────────────────
def load_config(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_status(cfg: dict[str, Any], **fields: Any) -> None:
    Path(cfg["status_path"]).write_text(json.dumps(fields, ensure_ascii=False, indent=2))


class MetricsWriter:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
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


def _is_oom(exc: BaseException) -> bool:
    try:
        import torch
        if isinstance(exc, torch.cuda.OutOfMemoryError):
            return True
    except Exception:
        pass
    text = str(exc).lower()
    return "out of memory" in text or "cuda oom" in text or ("alloc" in text and "memory" in text)


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


def _deepspeed_ok() -> bool:
    try:
        import deepspeed  # noqa: F401
        return True
    except Exception:
        return False


def build_ds_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Inline copy of ``app.features.training.deepspeed_config.build_ds_config``
    (kept here so this script stays app-independent). ZeRO-3 / ZeRO-Infinity:
    offload params + optimizer to CPU RAM or NVMe so a model larger than VRAM
    trains to completion."""
    target = (cfg.get("offload_target") or "auto").lower()
    if target not in ("cpu", "nvme"):
        # Spill to NVMe only when the off-GPU state exceeds the machine's real host
        # RAM (injected as host_ram_gb); fall back to 100 GB if it wasn't provided.
        headroom = float(cfg.get("host_ram_gb") or 100)
        target = "nvme" if float(cfg.get("est_host_ram_gb") or 0) > headroom else "cpu"
    nvme_path = cfg.get("nvme_path") or cfg.get("offload_folder") or "offload"
    if target == "nvme":
        Path(nvme_path).mkdir(parents=True, exist_ok=True)

    off_opt: dict[str, Any] = {"device": target, "pin_memory": True}
    off_par: dict[str, Any] = {"device": target, "pin_memory": True}
    if target == "nvme":
        off_opt["nvme_path"] = nvme_path
        off_par["nvme_path"] = nvme_path

    ds: dict[str, Any] = {
        "bf16": {"enabled": bool(cfg.get("bf16", True))},
        "train_micro_batch_size_per_gpu": "auto",
        "gradient_accumulation_steps": "auto",
        "gradient_clipping": "auto",
        "zero_optimization": {
            "stage": 3,
            "offload_optimizer": off_opt,
            "offload_param": off_par,
            "overlap_comm": True,
            "contiguous_gradients": True,
            "sub_group_size": 1_000_000_000,
            "stage3_max_live_parameters": 100_000_000,
            "stage3_max_reuse_distance": 100_000_000,
            "stage3_param_persistence_threshold": 1_000_000,
            "stage3_gather_16bit_weights_on_model_save": True,
        },
    }
    if target == "nvme":
        ds["aio"] = {"block_size": 1_048_576, "queue_depth": 8, "thread_count": 1,
                     "single_submit": False, "overlap_events": True}
    return ds


# ── model construction ─────────────────────────────────────────────────────────
def build_arch_config_kwargs(arch: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Map an ArchitectureSpec dict → (model_type, transformers config kwargs).

    Mirrors ``app.features.architect.service.build_config_dict`` but kept inline so
    the trainer stays app-independent.
    """
    family = arch.get("family", "qwen3")
    h = int(arch.get("hidden_size", 768))
    inter = arch.get("intermediate_size") or 4 * h
    kv = arch.get("num_key_value_heads") or arch.get("num_attention_heads", 12)
    kwargs: dict[str, Any] = {
        "hidden_size": h,
        "num_hidden_layers": int(arch.get("num_hidden_layers", 12)),
        "num_attention_heads": int(arch.get("num_attention_heads", 12)),
        "num_key_value_heads": int(kv),
        "intermediate_size": int(inter),
        "vocab_size": int(arch.get("vocab_size", 32000)),
        "max_position_embeddings": int(arch.get("max_position_embeddings", 2048)),
        "tie_word_embeddings": bool(arch.get("tie_word_embeddings", True)),
    }
    if family in ("qwen3_moe", "mixtral"):
        kwargs.update({
            "num_experts": int(arch.get("num_experts", 8)),
            "num_local_experts": int(arch.get("num_experts", 8)),
            "num_experts_per_tok": int(arch.get("num_experts_per_tok", 2)),
            "moe_intermediate_size": int(arch.get("moe_intermediate_size") or inter),
        })
    return family, kwargs


def load_tokenizer(cfg: dict[str, Any]):
    from transformers import AutoTokenizer
    # Pretrained embedding → adopt its tokenizer so vocab/embeddings line up.
    # Otherwise use an explicit tokenizer_repo, falling back to a small standard
    # tokenizer (a from-scratch model still needs *some* tokenizer to read text).
    repo = (cfg.get("embedding_source_repo") if cfg.get("embedding_mode") == "pretrained"
            else None) or cfg.get("tokenizer_repo") or "gpt2"
    tok = AutoTokenizer.from_pretrained(repo, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token or tok.unk_token
    return tok, repo


def build_model(cfg: dict[str, Any], tokenizer, metrics: MetricsWriter, ds_config=None):
    import torch
    from transformers import AutoConfig, AutoModelForCausalLM

    arch = cfg.get("architecture") or {}
    family, kwargs = build_arch_config_kwargs(arch)
    # Keep vocab consistent with the actual tokenizer (so no resize is needed).
    kwargs["vocab_size"] = len(tokenizer)

    hf_cfg = AutoConfig.for_model(family, **kwargs)
    hf_cfg.torch_dtype = torch.bfloat16
    try:
        hf_cfg.attn_implementation = "sdpa"   # Blackwell sm_120: no flash-attn build
    except Exception:
        pass

    if ds_config is not None:
        # ZeRO-3: partition parameters at construction so a model too big for even
        # CPU RAM can still be built (sharded straight to its offload home).
        import deepspeed
        with deepspeed.zero.Init(config_dict_or_path=ds_config, dtype=torch.bfloat16):
            model = AutoModelForCausalLM.from_config(hf_cfg)
    else:
        model = AutoModelForCausalLM.from_config(hf_cfg).to(torch.bfloat16)

    n_params = sum(getattr(p, "ds_numel", p.numel()) for p in model.parameters())
    metrics.emit({"event": "model_built", "family": family, "params": int(n_params),
                  "vocab_size": len(tokenizer)})

    # Pretrained embedding: copy input embeddings (best-effort; trainable either way).
    if cfg.get("embedding_mode") == "pretrained" and cfg.get("embedding_source_repo"):
        _load_pretrained_embedding(cfg["embedding_source_repo"], model, tokenizer, cfg,
                                   metrics, ds_active=ds_config is not None)

    # Embeddings are trainable (full training trains everything; the corpus may add
    # vocabulary). Under ZeRO-3 the flags still apply to the sharded params.
    model.get_input_embeddings().weight.requires_grad_(True)
    if model.get_output_embeddings() is not None:
        model.get_output_embeddings().weight.requires_grad_(True)
    return model


def _load_pretrained_embedding(source_repo: str, model, tokenizer, cfg, metrics,
                               ds_active: bool = False):
    """Copy the embedding matrix from ``source_repo`` into the new model.

    Only copies when the hidden dimension matches; rows are copied up to the
    smaller vocab. The layer stays trainable. On any mismatch we warn and keep
    the random init rather than crash. Under ZeRO-3 the destination param is
    sharded, so the copy happens inside a gathered context on rank 0.
    """
    import contextlib

    from transformers import AutoModel
    try:
        src = AutoModel.from_pretrained(source_repo, trust_remote_code=True,
                                        cache_dir=cfg.get("hf_cache"))
        src_emb = src.get_input_embeddings().weight.data
        dst_param = model.get_input_embeddings().weight

        gather = contextlib.nullcontext()
        if ds_active:
            import deepspeed
            gather = deepspeed.zero.GatheredParameters([dst_param], modifier_rank=0)
        with gather:
            dst_emb = dst_param.data
            if src_emb.shape[1] != dst_emb.shape[1]:
                metrics.emit({"event": "embedding_warn",
                              "message": f"hidden_size mismatch ({src_emb.shape[1]} vs "
                                         f"{dst_emb.shape[1]}); keeping random embedding."})
            else:
                rows = min(src_emb.shape[0], dst_emb.shape[0])
                dst_emb[:rows] = src_emb[:rows].to(dst_emb.dtype)
                metrics.emit({"event": "embedding_loaded", "source": source_repo,
                              "rows": int(rows)})
        del src
        _free_gpu()
    except Exception as exc:  # noqa: BLE001
        metrics.emit({"event": "embedding_warn",
                      "message": f"could not load pretrained embedding: {exc}"})


def place_model(cfg: dict[str, Any], model, metrics: MetricsWriter):
    """Put the model on the GPU, or — in paged mode — dispatch it across
    GPU→CPU→disk against a VRAM budget so a large model still fits.

    Paged dispatch makes each step far slower and is best-effort: some
    architectures don't train cleanly with offloaded parameters. The caller's
    broad except + OOM retry is the safety net.
    """
    import torch
    if not torch.cuda.is_available():
        metrics.emit({"event": "place", "device": "cpu"})
        return model

    if cfg.get("paged_training"):
        from accelerate import dispatch_model, infer_auto_device_map
        gpu_budget = int(cfg.get("gpu_budget_gb") or 0)
        if not gpu_budget:
            total = torch.cuda.get_device_properties(0).total_memory
            gpu_budget = max(1, int(total / (1024 ** 3)) - 1)
        cpu_gib = int(cfg.get("cpu_offload_gb", 96))
        offload = cfg.get("offload_folder") or "offload"
        Path(offload).mkdir(parents=True, exist_ok=True)
        max_mem = {0: f"{gpu_budget}GiB", "cpu": f"{cpu_gib}GiB"}
        device_map = infer_auto_device_map(model, max_memory=max_mem,
                                           no_split_module_classes=_no_split(model))
        model = dispatch_model(model, device_map=device_map, offload_dir=offload)
        metrics.emit({"event": "paged_mode", "gpu_budget_gb": gpu_budget,
                      "cpu_offload_gb": cpu_gib, **gpu_mem()})
        return model

    model = model.to("cuda")
    metrics.emit({"event": "place", "device": "cuda", **gpu_mem()})
    return model


def _no_split(model) -> list[str]:
    cls = getattr(model, "_no_split_modules", None)
    return list(cls) if cls else []


# ── data ────────────────────────────────────────────────────────────────────────
def _dataset_specs(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize the config into a list of corpus specs (multi-dataset aware).

    Prefers ``cfg["datasets"]`` (a list of ``{repo, config, split, text_field,
    max_samples}``); falls back to the legacy single ``dataset_repo`` fields so
    older projects keep working.
    """
    out: list[dict[str, Any]] = []
    for d in (cfg.get("datasets") or []):
        repo = (d or {}).get("repo")
        if not repo:
            continue
        out.append({
            "repo": repo,
            "config": d.get("config") or None,
            "split": d.get("split") or "train",
            "text_field": d.get("text_field") or "text",
            "max_samples": int(d.get("max_samples") or 0),
        })
    if out:
        return out
    repo = cfg.get("dataset_repo")
    if repo:
        return [{
            "repo": repo, "config": cfg.get("dataset_config") or None,
            "split": cfg.get("dataset_split") or "train",
            "text_field": cfg.get("text_field") or "text", "max_samples": 0,
        }]
    return []


def load_corpus(cfg: dict[str, Any], tokenizer, metrics: MetricsWriter):
    from datasets import concatenate_datasets, load_dataset
    specs = _dataset_specs(cfg)
    if not specs:
        raise ValueError("From-scratch training needs at least one corpus: set "
                         "datasets (search HuggingFace datasets in the wizard).")
    seq = int(cfg.get("max_seq_len", 1024))

    parts = []
    failures: list[tuple[str, str]] = []
    for spec in specs:
        # One bad corpus (typo, private/gated, removed, network) must NOT kill the
        # whole run — skip it with a loud metric and train on what loaded.
        try:
            ds = load_dataset(spec["repo"], spec["config"], split=spec["split"],
                              cache_dir=cfg.get("hf_cache"))
            field = spec["text_field"]
            if field not in ds.column_names:
                # fall back to the first column that looks like text
                field = next((c for c in ds.column_names), None)
                if field is None:
                    raise ValueError("dataset has no columns to train on")
            if spec["max_samples"] and len(ds) > spec["max_samples"]:
                ds = ds.select(range(spec["max_samples"]))

            # ``_field`` default-arg pins the loop var so each map closes over its own.
            def _tok(batch, _field=field):
                return tokenizer([str(t) for t in batch[_field]], truncation=True, max_length=seq)

            ds = ds.map(_tok, batched=True, remove_columns=ds.column_names)
            parts.append(ds)
            metrics.emit({"event": "dataset", "repo": spec["repo"], "text_field": field,
                          "num_examples": len(ds)})
        except Exception as exc:  # noqa: BLE001 — resilience over strictness
            msg = (str(exc).strip().splitlines() or [""])[0][:200] or type(exc).__name__
            failures.append((spec["repo"], msg))
            metrics.emit({"event": "dataset_error", "repo": spec["repo"], "error": msg})

    if not parts:
        detail = "; ".join(f"{r} ({m})" for r, m in failures) or "unknown error"
        raise ValueError(
            f"No dataset could be loaded — check the repo ids / your connection. "
            f"Failed: {detail}")
    if failures:
        metrics.emit({"event": "notice", "message":
                      f"Skipped {len(failures)} dataset(s) that failed to load: "
                      + ", ".join(r for r, _ in failures)})

    # Concatenate every corpus, shuffle so they interleave, then apply the global
    # cap (max_train_samples) over the combined set.
    ds = parts[0] if len(parts) == 1 else concatenate_datasets(parts)
    ds = ds.shuffle(seed=int(cfg.get("seed", 42)))
    cap = int(cfg.get("max_train_samples") or 0)
    if cap and len(ds) > cap:
        ds = ds.select(range(cap))
    metrics.emit({"event": "dataset_total", "num_datasets": len(parts),
                  "num_skipped": len(failures), "num_examples": len(ds)})
    return ds


# ── training ──────────────────────────────────────────────────────────────────
def build_trainer(cfg: dict[str, Any], model, tokenizer, dataset, metrics: MetricsWriter,
                  ds_config_path: str | None = None):
    from transformers import (DataCollatorForLanguageModeling, Trainer,
                              TrainerCallback, TrainingArguments)

    total_holder = {"total": int(cfg.get("_total_steps", 0))}

    class LiveCallback(TrainerCallback):
        def on_train_begin(self, args, state, control, **kw):
            total_holder["total"] = state.max_steps or total_holder["total"]
            metrics.emit({"event": "begin", "total_steps": total_holder["total"], **gpu_mem()})

        def on_log(self, args, state, control, logs=None, **kw):
            if not logs:
                return
            metrics.emit({
                "event": "log",
                "step": state.global_step,
                "total_steps": total_holder["total"] or state.max_steps,
                "epoch": round(state.epoch or 0, 3),
                "loss": logs.get("loss"),
                "learning_rate": logs.get("learning_rate"),
                "grad_norm": logs.get("grad_norm"),
                **gpu_mem(),
            })

    # Under DeepSpeed, let HF/DeepSpeed own the optimizer (it substitutes the
    # offloaded DeepSpeedCPUAdam for ZeRO-Infinity); the bnb paged optimizer is
    # only for the non-DeepSpeed fallback path.
    optim = "adamw_torch" if ds_config_path else cfg.get("optim", "paged_adamw_8bit")
    args = TrainingArguments(
        output_dir=cfg["output_dir"],
        num_train_epochs=float(cfg.get("epochs", 1)),
        per_device_train_batch_size=int(cfg.get("per_device_batch_size", 1)),
        gradient_accumulation_steps=int(cfg.get("grad_accum_steps", 16)),
        learning_rate=float(cfg.get("learning_rate", 3e-4)),
        lr_scheduler_type=cfg.get("lr_scheduler_type", "cosine"),
        warmup_ratio=float(cfg.get("warmup_ratio", 0.02)),
        weight_decay=float(cfg.get("weight_decay", 0.1)),
        bf16=bool(cfg.get("bf16", True)),
        optim=optim,
        deepspeed=ds_config_path,
        logging_steps=1,
        save_strategy="no",
        report_to=[],
        seed=int(cfg.get("seed", 42)),
        gradient_checkpointing=bool(cfg.get("gradient_checkpointing", True)),
    )
    collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)
    trainer = Trainer(model=model, args=args, train_dataset=dataset,
                      data_collator=collator, callbacks=[LiveCallback()])
    return trainer


def _one_attempt(cfg: dict[str, Any], metrics: MetricsWriter) -> dict[str, Any]:
    model = tokenizer = trainer = None
    # ZeRO-Infinity: the real "train bigger than VRAM to completion" path. Build
    # the config + HfDeepSpeedConfig BEFORE the model so ZeRO-3 partitions at init.
    want_paged = bool(cfg.get("paged_training"))
    ds_config = ds_config_path = dschf = None
    backend = "from_scratch"
    if want_paged and _deepspeed_ok():
        ds_config = build_ds_config(cfg)
        run_dir = Path(cfg["metrics_path"]).parent
        ds_config_path = str(run_dir / "ds_config.json")
        Path(ds_config_path).write_text(json.dumps(ds_config, ensure_ascii=False, indent=2))
        from transformers.integrations import HfDeepSpeedConfig
        dschf = HfDeepSpeedConfig(ds_config)   # must stay alive through model build
        backend = "zero_infinity"
        metrics.emit({"event": "zero_infinity",
                      "offload_target": ds_config["zero_optimization"]["offload_param"]["device"]})
    elif want_paged:
        metrics.emit({"event": "notice", "message":
                      "DeepSpeed not available — falling back to single-GPU placement. "
                      "A model larger than VRAM may not finish without DeepSpeed."})
    try:
        tokenizer, tok_repo = load_tokenizer(cfg)
        metrics.emit({"event": "tokenizer", "repo": tok_repo, "vocab_size": len(tokenizer)})
        model = build_model(cfg, tokenizer, metrics, ds_config=ds_config)
        if bool(cfg.get("gradient_checkpointing", True)):
            model.gradient_checkpointing_enable()
            model.config.use_cache = False
        if ds_config is None:
            model = place_model(cfg, model, metrics)

        dataset = load_corpus(cfg, tokenizer, metrics)
        trainer = build_trainer(cfg, model, tokenizer, dataset, metrics,
                                ds_config_path=ds_config_path)
        result = trainer.train()

        out = cfg["output_dir"]
        Path(out).mkdir(parents=True, exist_ok=True)
        trainer.save_model(out)
        tokenizer.save_pretrained(out)
        return {
            "adapter_path": out,          # full checkpoint dir (reuses the field name)
            "train_loss": float(result.training_loss) if result and result.training_loss else None,
            "backend": backend,
            "max_seq_len": int(cfg.get("max_seq_len", 1024)),
            **gpu_mem(),
        }
    finally:
        del trainer, model, tokenizer, dschf
        _free_gpu()


# ── main ────────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    cfg = load_config(ap.parse_args().config)

    _disable_httpx_brotli()   # avoid the httpx/brotli download crash (hub 1.x)

    metrics = MetricsWriter(cfg["metrics_path"])
    print(f"[train_scratch] starting run {cfg.get('run_id')} arch={cfg.get('architecture')}",
          flush=True)
    write_status(cfg, status="running")
    metrics.emit({"event": "notice", "message":
                  "From-scratch training is experimental: paging fits memory but cannot "
                  "supply the compute/data a real pretraining run needs."})

    try:
        min_seq = int(cfg.get("min_seq_len", 128))
        max_retries = int(cfg.get("oom_max_retries", 3))
        last_tb = ""
        for attempt in range(max_retries + 1):
            try:
                final_metrics = _one_attempt(cfg, metrics)
                metrics.emit({"event": "done", **final_metrics})
                write_status(cfg, status="completed",
                             adapter_path=final_metrics["adapter_path"], metrics=final_metrics)
                print("[train_scratch] completed", flush=True)
                return 0
            except BaseException as exc:  # noqa: BLE001
                oom = _is_oom(exc)
                msg = str(exc)[:500]
                last_tb = traceback.format_exc()
            _free_gpu()
            cur = int(cfg.get("max_seq_len", 1024))
            if oom and cur > min_seq:
                new_len = max(min_seq, cur // 2)
                cfg["max_seq_len"] = new_len
                metrics.emit({"event": "oom_retry", "old_seq_len": cur,
                              "new_seq_len": new_len, "attempt": attempt + 1})
                print(f"[train_scratch] CUDA OOM → retry {attempt + 1} at max_seq_len={new_len}",
                      flush=True)
                continue
            print(last_tb, file=sys.stderr, flush=True)
            reason = ("CUDA out of memory even at the minimum sequence length. A model "
                      "this size cannot train from scratch on this GPU — reduce the "
                      "architecture or context.\n\n" if oom else "") + msg
            metrics.emit({"event": "error", "error": reason})
            write_status(cfg, status="failed", error=f"{reason}\n\n{last_tb}")
            return 1
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        print(tb, file=sys.stderr, flush=True)
        metrics.emit({"event": "error", "error": str(exc)})
        write_status(cfg, status="failed", error=f"{exc}\n\n{tb}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
