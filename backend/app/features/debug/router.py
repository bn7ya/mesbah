"""HTTP routes for the debug/status panel."""
from __future__ import annotations

from fastapi import APIRouter

from . import service

router = APIRouter(prefix="/api/debug", tags=["debug"])


@router.get("/status")
def status():
    """Live system snapshot: hardware, GPU utilization, engine, downloads, runs."""
    return service.status()


@router.get("/logs")
def logs(lines: int = 200):
    """The last N backend log lines (in-memory ring buffer, newest last)."""
    return {"lines": service.recent_logs(lines)}
