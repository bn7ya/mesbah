"""HTTP + WebSocket routes for the auto-enhance loop.

The WebSocket at ``/api/auto-enhance/loops/{id}/ws`` tails the loop's
``events.jsonl`` (the live discussion/evaluation/training transcript) and polls
the loop's DB status, mirroring the training run WS.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import (APIRouter, Depends, HTTPException, WebSocket,
                     WebSocketDisconnect)
from sqlmodel import Session, select

from ...core.config import settings
from ...core.db import engine as db_engine
from ...core.db import get_session
from ...core.models import AutoEnhanceLoop, Project, RunStatus
from .manager import manager
from .schemas import LoopCreate

router = APIRouter(prefix="/api", tags=["auto-enhance"])

TERMINAL = {RunStatus.completed, RunStatus.failed, RunStatus.cancelled}


@router.get("/projects/{project_id}/auto-enhance/loops", response_model=list[AutoEnhanceLoop])
def list_loops(project_id: str, db: Session = Depends(get_session)):
    stmt = select(AutoEnhanceLoop).where(
        AutoEnhanceLoop.project_id == project_id
    ).order_by(AutoEnhanceLoop.created_at.desc())
    return list(db.exec(stmt).all())


@router.post("/projects/{project_id}/auto-enhance/loops",
             response_model=AutoEnhanceLoop, status_code=201)
def create_loop(project_id: str, data: LoopCreate, db: Session = Depends(get_session)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    busy = manager.busy_reason()
    if busy:
        raise HTTPException(409, busy)

    # Freeze the resolved config so a restart reads exactly what was launched.
    config = {
        "generations": data.generations,
        "turns_per_generation": data.turns_per_generation,
        "thresholds": data.thresholds.model_dump(),
        "max_correction_rounds": data.max_correction_rounds,
        "topic_source": data.topic_source,
        "hyperparams": data.hyperparams,
        "parent_version_id": data.parent_version_id or project.active_version_id,
        "ask_prompt": data.ask_prompt or settings.default_ask_prompt,
        "eval_prompt": data.eval_prompt or settings.default_eval_prompt,
    }
    loop = AutoEnhanceLoop(
        project_id=project_id,
        name=data.name or "تحسين تلقائي",
        status=RunStatus.pending,
        config=config,
    )
    db.add(loop)
    db.commit()
    db.refresh(loop)

    try:
        manager.start(loop.id)
    except RuntimeError as exc:
        loop.status = RunStatus.failed
        loop.error = str(exc)
        db.add(loop)
        db.commit()
        db.refresh(loop)
        raise HTTPException(409, str(exc)) from exc
    db.refresh(loop)
    return loop


@router.get("/auto-enhance/loops/{loop_id}", response_model=AutoEnhanceLoop)
def get_loop(loop_id: str, db: Session = Depends(get_session)):
    loop = db.get(AutoEnhanceLoop, loop_id)
    if not loop:
        raise HTTPException(404, "Loop not found")
    return loop


@router.post("/auto-enhance/loops/{loop_id}/cancel")
def cancel_loop(loop_id: str, db: Session = Depends(get_session)):
    loop = db.get(AutoEnhanceLoop, loop_id)
    if not loop:
        raise HTTPException(404, "Loop not found")
    ok = manager.cancel(loop_id)
    return {"cancelled": ok}


@router.websocket("/auto-enhance/loops/{loop_id}/ws")
async def loop_ws(websocket: WebSocket, loop_id: str):
    """Stream live loop events + terminal status to the dashboard."""
    await websocket.accept()
    events_file = manager.events_path(loop_id)
    offset = 0
    try:
        while True:
            if events_file.exists():
                with events_file.open("r", encoding="utf-8") as f:
                    f.seek(offset)
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                await websocket.send_json({"type": "event", "data": json.loads(line)})
                            except json.JSONDecodeError:
                                pass
                    offset = f.tell()

            status = _read_status(loop_id)
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


def _read_status(loop_id: str) -> dict[str, Any]:
    with Session(db_engine) as db:
        loop = db.get(AutoEnhanceLoop, loop_id)
        if not loop:
            return {}
        return {
            "status": loop.status.value,
            "progress": loop.progress,
            "results": loop.results,
            "error": loop.error,
        }
