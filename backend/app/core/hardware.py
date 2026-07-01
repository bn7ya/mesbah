"""Machine hardware detection + VRAM-driven training defaults.

Replaces the old hardcoded "RTX 5080 / 16 GB / 128 GB RAM" budget: we probe the
*actual* GPU(s) and system RAM, let the user pick which GPU on first run (stored in
``features/settings``), and derive QLoRA / from-scratch training knobs from whatever
VRAM + RAM the machine really has.

Probing is layered so the API still boots with no ML stack installed:
  GPUs  → pynvml → torch.cuda → ``nvidia-smi`` → [] (CPU-only)
  RAM   → psutil → os.sysconf (POSIX) → ctypes (Windows) → 0.0
Everything is best-effort and the static facts (GPU list, total RAM) are cached so
``/api/system`` stays cheap. ``refresh()`` clears the cache (e.g. after a re-pick).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any, Optional

# Static hardware facts, cached after first probe (they don't change at runtime).
_cache: dict[str, Any] = {}


# ── GPU probes (first non-empty wins) ─────────────────────────────────────────

def _gpus_via_pynvml() -> Optional[list[dict[str, Any]]]:
    try:
        import pynvml  # nvidia-ml-py
        pynvml.nvmlInit()
        try:
            out: list[dict[str, Any]] = []
            for i in range(pynvml.nvmlDeviceGetCount()):
                h = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(h)
                if isinstance(name, bytes):
                    name = name.decode()
                mem = pynvml.nvmlDeviceGetMemoryInfo(h)
                try:
                    major, minor = pynvml.nvmlDeviceGetCudaComputeCapability(h)
                    cc: Optional[str] = f"{major}.{minor}"
                except Exception:
                    cc = None
                out.append({
                    "index": i,
                    "name": name,
                    "total_vram_gb": round(mem.total / 1e9, 1),
                    "compute_capability": cc,
                })
            return out or None
        finally:
            pynvml.nvmlShutdown()
    except Exception:
        return None


def _gpus_via_torch() -> Optional[list[dict[str, Any]]]:
    try:
        import torch
        if not torch.cuda.is_available():
            return None
        out: list[dict[str, Any]] = []
        for i in range(torch.cuda.device_count()):
            p = torch.cuda.get_device_properties(i)
            out.append({
                "index": i,
                "name": p.name,
                "total_vram_gb": round(p.total_memory / 1e9, 1),
                "compute_capability": f"{p.major}.{p.minor}",
            })
        return out or None
    except Exception:
        return None


def _gpus_via_nvidia_smi() -> Optional[list[dict[str, Any]]]:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        res = subprocess.run(
            [exe, "--query-gpu=index,name,memory.total,compute_cap",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if res.returncode != 0:
            return None
        out: list[dict[str, Any]] = []
        for line in res.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 3:
                continue
            mib = float(parts[2])  # MiB
            cc = parts[3] if len(parts) > 3 and parts[3] not in ("", "[N/A]") else None
            out.append({
                "index": int(parts[0]),
                "name": parts[1],
                "total_vram_gb": round(mib * 1_048_576 / 1e9, 1),  # MiB → decimal GB
                "compute_capability": cc,
            })
        return out or None
    except Exception:
        return None


def detect_gpus(refresh: bool = False) -> list[dict[str, Any]]:
    """All CUDA GPUs as ``[{index, name, total_vram_gb, compute_capability}]`` (cached)."""
    if not refresh and "gpus" in _cache:
        return _cache["gpus"]
    gpus = _gpus_via_pynvml() or _gpus_via_torch() or _gpus_via_nvidia_smi() or []
    _cache["gpus"] = gpus
    return gpus


# ── RAM probe ─────────────────────────────────────────────────────────────────

def detect_system_ram_gb() -> float:
    try:
        import psutil
        return round(psutil.virtual_memory().total / 1e9, 1)
    except Exception:
        pass
    try:  # POSIX
        if hasattr(os, "sysconf") and "SC_PHYS_PAGES" in os.sysconf_names:
            total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
            return round(total / 1e9, 1)
    except Exception:
        pass
    try:  # Windows
        import ctypes

        class _MemStatus(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        stat = _MemStatus()
        stat.dwLength = ctypes.sizeof(_MemStatus)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))  # type: ignore[attr-defined]
        return round(stat.ullTotalPhys / 1e9, 1)
    except Exception:
        pass
    return 0.0


def system_ram_gb(refresh: bool = False) -> float:
    if not refresh and "ram" in _cache:
        return _cache["ram"]
    ram = detect_system_ram_gb()
    _cache["ram"] = ram
    return ram


def refresh() -> None:
    """Drop the cached hardware probe (call after the user re-picks the GPU)."""
    _cache.clear()


# ── effective selection (honours the user's first-run / settings choice) ──────

def effective_gpus() -> list[dict[str, Any]]:
    """The GPU(s) training should target: the user-selected indices (in order),
    else the single largest detected GPU. Empty on a CPU-only box."""
    gpus = detect_gpus()
    if not gpus:
        return []
    try:
        from ..features.settings import service as settings_store
        indices = settings_store.selected_gpu_indices()
    except Exception:
        indices = None
    if indices:
        by_index = {g["index"]: g for g in gpus}
        chosen = [by_index[i] for i in indices if i in by_index]
        if chosen:
            return chosen
    return [max(gpus, key=lambda g: g.get("total_vram_gb", 0))]


def effective_gpu() -> Optional[dict[str, Any]]:
    """First selected GPU (back-compat for single-GPU callers)."""
    gpus = effective_gpus()
    return gpus[0] if gpus else None


def effective_vram_gb() -> float:
    """Usable VRAM (GB): a manual override if set, else the **sum** across the
    selected GPUs (device_map sharding lets training use them together)."""
    try:
        from ..features.settings import service as settings_store
        override = settings_store.vram_override_gb()
    except Exception:
        override = None
    if override:
        return float(override)
    return float(sum(g.get("total_vram_gb", 0) for g in effective_gpus()))


def snapshot() -> dict[str, Any]:
    """Hardware summary for ``GET /api/system`` and the first-run GPU picker."""
    gpus = detect_gpus()
    selected = effective_gpus()
    return {
        "gpus": gpus,
        "selected_gpu": selected[0] if selected else None,   # back-compat
        "selected_gpus": selected,
        "gpu_vram_gb": effective_vram_gb(),
        "system_ram_gb": system_ram_gb(),
        "cuda_available": bool(gpus),
    }


# ── VRAM/RAM → training defaults ──────────────────────────────────────────────

_EFFECTIVE_BATCH = 16   # micro-batch × grad-accum target


def compute_train_defaults(vram_gb: float, ram_gb: float, *, kind: str = "finetune",
                           model_params_b: Optional[float] = None) -> dict[str, Any]:
    """Derive memory-sensitive training knobs from real VRAM + RAM.

    One heuristic table keyed by VRAM tiers, replacing the old fixed 16 GB numbers.
    QLoRA (``finetune``) fits much longer context than full ``scratch`` training, so
    the sequence-length ladder differs by ``kind``. All values stay overridable by
    the project's advanced settings / per-run hyperparams.
    """
    vram = max(0.0, float(vram_gb or 0))
    ram = max(0.0, float(ram_gb or 0))

    # Tier boundaries carry ~2 GB headroom so a nominal "16 GB" card (which reports
    # ~16.6 GB) lands on the 16 GB rung, not the next one up.
    if kind == "scratch":
        seq = 512 if vram < 10 else 1024 if vram < 18 else 2048 if vram < 28 else 4096
    else:
        seq = (2048 if vram < 10 else 3072 if vram < 14 else 4096 if vram < 18
               else 8192 if vram < 28 else 16384)

    # Bigger cards can hold a larger micro-batch; grad-accum lifts the effective
    # batch back toward ~16 regardless.
    batch = 1 if vram < 18 else 2 if vram < 28 else 4 if vram < 50 else 8
    grad_accum = max(1, round(_EFFECTIVE_BATCH / batch))

    # LoRA rank scales with capacity (alpha = 2·r, the Unsloth-friendly default).
    lora_r = 8 if vram < 8 else 16 if vram < 24 else 32 if vram < 48 else 64

    gpu_budget = max(1, int(vram) - 1) if vram >= 2 else 1
    cpu_offload = int(max(0, ram * 0.75))   # leave ~25% host RAM for the OS

    return {
        "max_seq_len": seq,
        "per_device_batch_size": batch,
        "grad_accum_steps": grad_accum,
        "lora_r": lora_r,
        "lora_alpha": lora_r * 2,
        "gpu_budget_gb": gpu_budget,
        "cpu_offload_gb": cpu_offload,
        "vram_gb": round(vram, 1),
        "ram_gb": round(ram, 1),
    }


def train_defaults(kind: str = "finetune", model_params_b: Optional[float] = None) -> dict[str, Any]:
    """``compute_train_defaults`` fed with this machine's effective VRAM + RAM.

    With multiple selected GPUs the VRAM is the aggregate across them (the
    trainer shards via device_map), reported alongside ``num_gpus``."""
    out = compute_train_defaults(effective_vram_gb(), system_ram_gb(),
                                 kind=kind, model_params_b=model_params_b)
    out["num_gpus"] = len(effective_gpus())
    return out
