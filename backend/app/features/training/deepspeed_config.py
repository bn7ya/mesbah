"""Build a DeepSpeed ZeRO-Infinity config for from-scratch full training.

ZeRO stage 3 with parameter + optimizer + gradient offload to CPU RAM (and, for
models too big for RAM, NVMe) is what lets a model larger than the 16 GB GPU train
**to completion**: only the layer currently being computed lives on the GPU, the
rest streams from host RAM / SSD. It's slow — bounded by RAM/PCIe/NVMe bandwidth —
but it finishes, which is the whole point.

Pure dict construction, **no torch import** — safe to import at the API layer. The
trainer subprocess keeps an inline copy (see ``scripts/train_scratch.py``) so it
stays app-independent; this module is the single source of truth for the shape and
is what ``manager.prepare`` uses to record the resolved settings.

``offload_target``:
  * ``cpu``  — params/optimizer in pinned host RAM (fastest offload; needs the model
               to fit in RAM, ~params×(2 grad + 4 fp32-master + 8 Adam) bytes).
  * ``nvme`` — spill to an NVMe directory; for models that don't fit RAM either.
  * ``auto`` — pick by the estimated host-RAM footprint vs ~100 GB headroom.
"""
from __future__ import annotations

from typing import Any

# Fallback host-RAM headroom (GB) when the machine's real RAM isn't injected.
_RAM_HEADROOM_GB = 100


def resolve_offload_target(cfg: dict[str, Any]) -> str:
    target = (cfg.get("offload_target") or "auto").lower()
    if target in ("cpu", "nvme"):
        return target
    # auto: full training holds ~ params × (2 bf16 grad + 4 fp32 master + 8 Adam)
    # bytes of state off-GPU. Estimate from the architecture if available.
    est_ram = float(cfg.get("est_host_ram_gb") or 0)
    headroom = float(cfg.get("host_ram_gb") or _RAM_HEADROOM_GB)
    return "nvme" if est_ram > headroom else "cpu"


def build_ds_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Return a ZeRO-3 (ZeRO-Infinity) DeepSpeed config dict for ``cfg``."""
    target = resolve_offload_target(cfg)
    nvme_path = cfg.get("nvme_path") or cfg.get("offload_folder") or "offload"

    offload_optimizer: dict[str, Any] = {"device": target, "pin_memory": True}
    offload_param: dict[str, Any] = {"device": target, "pin_memory": True}
    if target == "nvme":
        offload_optimizer["nvme_path"] = nvme_path
        offload_param["nvme_path"] = nvme_path

    ds: dict[str, Any] = {
        "bf16": {"enabled": bool(cfg.get("bf16", True))},
        # HF Trainer fills these from TrainingArguments ("auto").
        "train_micro_batch_size_per_gpu": "auto",
        "gradient_accumulation_steps": "auto",
        "gradient_clipping": "auto",
        "zero_optimization": {
            "stage": 3,
            "offload_optimizer": offload_optimizer,
            "offload_param": offload_param,
            "overlap_comm": True,
            "contiguous_gradients": True,
            "sub_group_size": 1_000_000_000,
            "stage3_max_live_parameters": 100_000_000,
            "stage3_max_reuse_distance": 100_000_000,
            "stage3_param_persistence_threshold": 1_000_000,
            # Gather sharded params back to fp16/bf16 when saving the checkpoint.
            "stage3_gather_16bit_weights_on_model_save": True,
        },
    }
    if target == "nvme":
        # Async-IO tuning for NVMe streaming (needs libaio at runtime).
        ds["aio"] = {
            "block_size": 1_048_576,
            "queue_depth": 8,
            "thread_count": 1,
            "single_submit": False,
            "overlap_events": True,
        }
    return ds
