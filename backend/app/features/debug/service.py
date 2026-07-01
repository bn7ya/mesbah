"""Debug/status snapshot for the GUI's debug panel.

Everything here is best-effort and import-light: the endpoint must answer even
when the ML stack is missing, a GPU probe fails, or nothing is running. Live GPU
utilization comes from pynvml when available, else ``nvidia-smi``, else ``[]``.
"""
from __future__ import annotations

import logging
import platform
import shutil
import subprocess
from collections import deque
from typing import Any

# ── in-memory log ring buffer ─────────────────────────────────────────────────

_LOG_CAPACITY = 500


class RingBufferHandler(logging.Handler):
    """Keeps the last N formatted log records in memory for /api/debug/logs."""

    def __init__(self, capacity: int = _LOG_CAPACITY) -> None:
        super().__init__()
        self.buffer: deque[str] = deque(maxlen=capacity)
        self.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s — %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.buffer.append(self.format(record))
        except Exception:  # never let logging take the app down
            pass


_handler: RingBufferHandler | None = None


def install_log_buffer() -> None:
    """Attach the ring buffer to the root + uvicorn loggers (idempotent; call at
    startup). uvicorn's loggers don't propagate to root, so hook them directly."""
    global _handler
    if _handler is None:
        _handler = RingBufferHandler()
        # "uvicorn.error" propagates into "uvicorn", so hooking it too would
        # duplicate records; "uvicorn.access" has propagate=False and needs its own.
        for name in (None, "uvicorn", "uvicorn.access"):
            logging.getLogger(name).addHandler(_handler)


def recent_logs(lines: int = 200) -> list[str]:
    if _handler is None:
        return []
    buf = list(_handler.buffer)
    return buf[-max(1, min(lines, _LOG_CAPACITY)):]


# ── live GPU utilization ──────────────────────────────────────────────────────

def _gpu_live_pynvml() -> list[dict[str, Any]] | None:
    try:
        import pynvml
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
                    util = pynvml.nvmlDeviceGetUtilizationRates(h).gpu
                except Exception:
                    util = None
                try:
                    temp = pynvml.nvmlDeviceGetTemperature(
                        h, pynvml.NVML_TEMPERATURE_GPU)
                except Exception:
                    temp = None
                out.append({
                    "index": i,
                    "name": name,
                    "util_pct": util,
                    "mem_used_gb": round(mem.used / 1e9, 2),
                    "mem_total_gb": round(mem.total / 1e9, 2),
                    "temp_c": temp,
                })
            return out or None
        finally:
            pynvml.nvmlShutdown()
    except Exception:
        return None


def _gpu_live_nvidia_smi() -> list[dict[str, Any]] | None:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        res = subprocess.run(
            [exe, "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if res.returncode != 0:
            return None
        out: list[dict[str, Any]] = []
        for line in res.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 5:
                continue

            def num(v: str) -> float | None:
                try:
                    return float(v)
                except ValueError:
                    return None
            used = num(parts[3])
            total = num(parts[4])
            out.append({
                "index": int(parts[0]),
                "name": parts[1],
                "util_pct": num(parts[2]),
                "mem_used_gb": round(used * 1_048_576 / 1e9, 2) if used is not None else None,
                "mem_total_gb": round(total * 1_048_576 / 1e9, 2) if total is not None else None,
                "temp_c": num(parts[5]) if len(parts) > 5 else None,
            })
        return out or None
    except Exception:
        return None


def gpu_live() -> list[dict[str, Any]]:
    return _gpu_live_pynvml() or _gpu_live_nvidia_smi() or []


# ── environment facts ─────────────────────────────────────────────────────────

def _pkg_version(name: str) -> str | None:
    try:
        from importlib.metadata import version
        return version(name)
    except Exception:
        return None


def env_info() -> dict[str, Any]:
    return {
        "python": platform.python_version(),
        "torch": _pkg_version("torch"),
        "transformers": _pkg_version("transformers"),
        "ml_available": _pkg_version("torch") is not None,
    }


# ── full snapshot ─────────────────────────────────────────────────────────────

def status() -> dict[str, Any]:
    from ...core import hardware
    from ...core.db import engine as db_engine
    from ...core.models import RunStatus, TrainingRun
    from ..inference.engine import engine as inference_engine
    from ..models.service import manager as download_manager
    from ..settings import service as settings_store

    active_runs: list[dict[str, Any]] = []
    try:
        from sqlmodel import Session, select
        with Session(db_engine) as db:
            stmt = select(TrainingRun).where(
                TrainingRun.status.in_([RunStatus.running, RunStatus.preparing]))
            for run in db.exec(stmt).all():
                active_runs.append({
                    "id": run.id,
                    "name": run.name,
                    "project_id": run.project_id,
                    "status": run.status.value,
                    "pid": run.pid,
                    "started_at": run.started_at.isoformat() if run.started_at else None,
                })
    except Exception:
        pass

    try:
        engine_status = inference_engine.status()
    except Exception as exc:
        engine_status = {"error": str(exc)}

    return {
        "hardware": hardware.snapshot(),
        "gpu_live": gpu_live(),
        "engine": engine_status,
        "downloads": download_manager.list_all(),
        "active_runs": active_runs,
        "settings": {
            "selected_gpu_indices": settings_store.selected_gpu_indices(),
            "onboarded": settings_store.is_onboarded(),
        },
        "env": env_info(),
    }
