"""Persisted application settings (first-run onboarding, GPU choice, theme, tokens).

A tiny JSON store under ``data/app_settings.json`` — the same data-dir pattern as
the HuggingFace token file in ``features/models/service.py``. Kept deliberately
separate from ``core/config.Settings`` (env-derived, treated as immutable at
runtime): this holds the few things the *user* sets from the GUI and that must
survive restarts. No torch/ML imports — safe to read on boot and from any feature.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Optional

from ...core.config import settings as app_config

_LOCK = threading.Lock()

_DEFAULTS: dict[str, Any] = {
    "onboarded": False,
    "selected_gpu_index": None,    # legacy single choice (kept for back-compat reads)
    "selected_gpu_indices": None,  # None => use the largest detected GPU
    "gpu_vram_gb_override": None,   # None => use the detected VRAM
    "theme": "light",              # "light" | "dark"
    "tokens": {},                  # generic {name: secret} API tokens (HF has its own file)
}

# Keys a PATCH is allowed to set directly (``tokens`` is merged separately).
_ALLOWED = {"onboarded", "selected_gpu_index", "selected_gpu_indices",
            "gpu_vram_gb_override", "theme"}


def _path() -> Path:
    return app_config.data_dir / "app_settings.json"


def _read_raw() -> dict[str, Any]:
    path = _path()
    data = dict(_DEFAULTS)
    try:
        if path.exists():
            stored = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                data.update({k: stored.get(k, v) for k, v in _DEFAULTS.items()})
                for k, v in stored.items():      # keep unknown keys (forward-compatible)
                    data.setdefault(k, v)
    except (OSError, json.JSONDecodeError):
        pass
    return data


def _write_raw(data: dict[str, Any]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)   # best-effort: the file may hold API tokens
    except OSError:
        pass


# ── public accessors (used by core/hardware.py, main.py) ──────────────────────

def selected_gpu_index() -> Optional[int]:
    v = _read_raw().get("selected_gpu_index")
    return int(v) if isinstance(v, int) else None


def selected_gpu_indices() -> Optional[list[int]]:
    """The user's GPU choice as a list. The new multi-select key wins; a legacy
    single ``selected_gpu_index`` is wrapped as ``[idx]``. None ⇒ auto (largest)."""
    data = _read_raw()
    v = data.get("selected_gpu_indices")
    if isinstance(v, list):
        indices = [int(i) for i in v if isinstance(i, (int, float))]
        return indices or None
    legacy = data.get("selected_gpu_index")
    return [int(legacy)] if isinstance(legacy, int) else None


def vram_override_gb() -> Optional[float]:
    v = _read_raw().get("gpu_vram_gb_override")
    return float(v) if isinstance(v, (int, float)) and v else None


def is_onboarded() -> bool:
    return bool(_read_raw().get("onboarded"))


def get_token(name: str) -> Optional[str]:
    tok = (_read_raw().get("tokens") or {}).get(name)
    return tok or None


# ── views + mutation ──────────────────────────────────────────────────────────

def _hint(secret: str) -> str:
    return (secret[:3] + "…" + secret[-4:]) if secret and len(secret) > 8 else "…"


def public() -> dict[str, Any]:
    """Settings safe to send to the GUI — token *secrets* are masked to hints."""
    data = _read_raw()
    tokens = data.get("tokens") or {}
    return {
        "onboarded": bool(data.get("onboarded")),
        "selected_gpu_index": data.get("selected_gpu_index"),
        "selected_gpu_indices": selected_gpu_indices(),
        "gpu_vram_gb_override": data.get("gpu_vram_gb_override"),
        "theme": data.get("theme", "light"),
        "tokens": {name: {"configured": True, "hint": _hint(secret)}
                   for name, secret in tokens.items() if secret},
    }


def patch(updates: dict[str, Any]) -> dict[str, Any]:
    """Merge ``updates`` into the store. ``tokens`` is a shallow merge where an
    empty/falsy value removes that token; other keys overwrite."""
    with _LOCK:
        data = _read_raw()
        for key, value in updates.items():
            if key == "tokens" and isinstance(value, dict):
                tokens = dict(data.get("tokens") or {})
                for name, secret in value.items():
                    if secret:
                        tokens[name] = str(secret)
                    else:
                        tokens.pop(name, None)   # empty/null removes
                data["tokens"] = tokens
            elif key in _ALLOWED:
                data[key] = value
                # Keep the two GPU keys coherent so old readers of the legacy
                # single index still see something sensible.
                if key == "selected_gpu_indices":
                    data["selected_gpu_index"] = (
                        int(value[0]) if isinstance(value, list) and value else None)
                elif key == "selected_gpu_index":
                    data["selected_gpu_indices"] = (
                        [int(value)] if isinstance(value, int) else None)
        _write_raw(data)
    return public()


def onboard(selected_gpu_indices: Optional[list[int]]) -> dict[str, Any]:
    """Record the first-run GPU choice and flip the onboarded flag."""
    return patch({"onboarded": True, "selected_gpu_indices": selected_gpu_indices})
