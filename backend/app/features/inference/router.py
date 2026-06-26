"""Inference status + ad-hoc generation endpoints.

The chat workflow lives in the *sessions* feature; these endpoints expose the
engine directly for diagnostics ("is a model loaded? how much VRAM is free?")
and quick prompt testing.
"""
from __future__ import annotations

import os
import threading
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from ...core.db import get_session
from ...core.models import Project
from .engine import ModelRuntimeUnavailable, engine
from .service import resolve_weights

router = APIRouter(prefix="/api/inference", tags=["inference"])


class GenerateRequest(BaseModel):
    project_id: str
    version_id: Optional[str] = None
    prompt: str
    system_prompt: Optional[str] = None
    max_new_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None


class WarmupRequest(BaseModel):
    project_id: str
    version_id: Optional[str] = None


@router.get("/status")
def status():
    return engine.status()


@router.post("/unload")
def unload():
    """Free all VRAM. Called automatically when leaving a project workspace and
    before launching a training run."""
    engine.unload()
    return {"ok": True}


@router.post("/warmup")
def warmup(req: WarmupRequest, db: Session = Depends(get_session)):
    """Pre-load the project's active model into VRAM in the background.

    Called when entering a project so the first chat is instant. Loads ONLY when
    the base weights are already downloaded locally — never triggers a multi-GB
    HuggingFace download, and silently no-ops if the ML runtime is absent.
    """
    project = db.get(Project, req.project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if engine.frozen:
        return {"warming": False, "reason": "training_in_progress"}
    if not engine.status().get("runtime_available"):
        return {"warming": False, "reason": "runtime_unavailable"}

    # Resolve the weights for this (project, version). For an untrained scratch
    # project there is nothing to load yet.
    try:
        base_id, adapter_path, load_in_4bit = resolve_weights(db, project, req.version_id)
    except ValueError:
        return {"warming": False, "reason": "not_trained"}
    # Only warm from local weights — never trigger a multi-GB HuggingFace download.
    if not os.path.isdir(base_id):
        return {"warming": False, "reason": "model_not_local"}

    def _load():
        try:
            engine.ensure_loaded(base_id, adapter_path, load_in_4bit=load_in_4bit)
        except Exception:
            pass

    threading.Thread(target=_load, daemon=True).start()
    return {"warming": True, "base_id": base_id}


@router.post("/generate")
def generate(req: GenerateRequest, db: Session = Depends(get_session)):
    project = db.get(Project, req.project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    try:
        base_id, adapter_path, load_in_4bit = resolve_weights(db, project, req.version_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    messages = []
    if req.system_prompt:
        messages.append({"role": "system", "content": req.system_prompt})
    messages.append({"role": "user", "content": req.prompt})
    try:
        engine.ensure_loaded(base_id, adapter_path, load_in_4bit=load_in_4bit)
        text = engine.generate(
            messages,
            max_new_tokens=req.max_new_tokens,
            temperature=req.temperature,
            top_p=req.top_p,
        )
    except ModelRuntimeUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"text": text, "base_id": base_id, "adapter_path": adapter_path}
