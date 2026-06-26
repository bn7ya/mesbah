"""HTTP + WebSocket routes for training runs.

The WebSocket at ``/api/training/runs/{id}/ws`` tails the run's ``metrics.jsonl``
and forwards each new point to the GUI, so the loss curve and GPU-memory gauge
animate in real time. It also pushes terminal status so the dashboard can flip to
"completed/failed" without polling.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from fastapi import (APIRouter, Depends, HTTPException, WebSocket,
                     WebSocketDisconnect)
from pydantic import BaseModel
from sqlmodel import Session, select

from ...core.db import engine as db_engine
from ...core.db import get_session
from ...core.models import Project, RunStatus, TrainingRun
from . import dataset
from .manager import manager

router = APIRouter(prefix="/api", tags=["training"])

TERMINAL = {RunStatus.completed, RunStatus.failed, RunStatus.cancelled}


class RunCreate(BaseModel):
    name: str
    parent_version_id: Optional[str] = None        # None => fresh from base
    session_ids: Optional[list[str]] = None         # None => all sessions
    task_id: Optional[str] = None
    only_corrected: bool = False
    hyperparams: dict[str, Any] = {}
    autostart: bool = True


@router.get("/projects/{project_id}/training/preview")
def dataset_preview(project_id: str, task_id: Optional[str] = None,
                    only_corrected: bool = False, db: Session = Depends(get_session)):
    return dataset.preview(db, project_id, task_id=task_id, only_corrected=only_corrected)


@router.get("/projects/{project_id}/training/runs", response_model=list[TrainingRun])
def list_runs(project_id: str, db: Session = Depends(get_session)):
    stmt = select(TrainingRun).where(TrainingRun.project_id == project_id).order_by(
        TrainingRun.created_at.desc()
    )
    return list(db.exec(stmt).all())


@router.post("/projects/{project_id}/training/runs", response_model=TrainingRun, status_code=201)
def create_run(project_id: str, data: RunCreate, db: Session = Depends(get_session)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    parent = data.parent_version_id or project.active_version_id
    run = TrainingRun(
        project_id=project_id,
        name=data.name,
        parent_version_id=parent,
        config={
            "session_ids": data.session_ids,
            "task_id": data.task_id,
            "only_corrected": data.only_corrected,
            "hyperparams": data.hyperparams,
        },
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    run = manager.prepare(db, run)
    if run.num_examples == 0:
        run.status = RunStatus.failed
        run.error = "No approved training examples found. Correct and approve some replies first."
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    if data.autostart:
        manager.launch(run.id)
        db.refresh(run)
    return run


@router.get("/training/runs/{run_id}", response_model=TrainingRun)
def get_run(run_id: str, db: Session = Depends(get_session)):
    run = db.get(TrainingRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run


@router.post("/training/runs/{run_id}/start", response_model=TrainingRun)
def start_run(run_id: str, db: Session = Depends(get_session)):
    run = db.get(TrainingRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if run.status in TERMINAL:
        raise HTTPException(400, f"Run already {run.status.value}")
    manager.launch(run_id)
    db.refresh(run)
    return run


@router.post("/training/runs/{run_id}/cancel")
def cancel_run(run_id: str, db: Session = Depends(get_session)):
    run = db.get(TrainingRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    ok = manager.cancel(run_id)
    return {"cancelled": ok}


@router.websocket("/training/runs/{run_id}/ws")
async def run_ws(websocket: WebSocket, run_id: str):
    """Stream live metric points, raw trainer logs, and terminal status."""
    await websocket.accept()
    metrics_file = manager.metrics_path(run_id)
    log_file = manager.log_path(run_id)
    offset = 0          # byte offset into metrics.jsonl
    log_offset = 0      # byte offset into train.log
    try:
        while True:
            # forward any new metric lines
            if metrics_file.exists():
                with metrics_file.open("r", encoding="utf-8") as f:
                    f.seek(offset)
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                await websocket.send_json({"type": "metric", "data": json.loads(line)})
                            except json.JSONDecodeError:
                                pass
                    offset = f.tell()

            # forward any new raw terminal log lines (the trainer's stdout/stderr).
            # Binary read for exact byte offsets; only emit complete lines and keep a
            # trailing partial line for the next poll.
            if log_file.exists():
                with log_file.open("rb") as f:
                    f.seek(log_offset)
                    data = f.read()
                nl = data.rfind(b"\n")
                if nl >= 0:
                    consumed = data[:nl + 1]
                    log_offset += len(consumed)
                    for raw in consumed.split(b"\n"):
                        text = raw.decode("utf-8", "replace").rstrip("\r")
                        if text:
                            await websocket.send_json({"type": "log", "data": {"line": text}})

            # check run status (fresh session each poll)
            status = _read_status(run_id)
            await websocket.send_json({"type": "status", "data": status})
            if status and status.get("status") in {s.value for s in TERMINAL}:
                break
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


def _read_status(run_id: str) -> dict[str, Any]:
    from sqlmodel import Session as _S
    with _S(db_engine) as db:
        run = db.get(TrainingRun, run_id)
        if not run:
            return {}
        return {
            "status": run.status.value,
            "progress": run.progress,
            "metrics": run.metrics,
            "error": run.error,
            "result_version_id": run.result_version_id,
            "num_examples": run.num_examples,
        }
