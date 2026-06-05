"""Inference status + ad-hoc generation endpoints.

The chat workflow lives in the *sessions* feature; these endpoints expose the
engine directly for diagnostics ("is a model loaded? how much VRAM is free?")
and quick prompt testing.
"""
from __future__ import annotations

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


@router.get("/status")
def status():
    return engine.status()


@router.post("/unload")
def unload():
    """Free all VRAM (handy before launching a training run)."""
    engine.unload()
    return {"ok": True}


@router.post("/generate")
def generate(req: GenerateRequest, db: Session = Depends(get_session)):
    project = db.get(Project, req.project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    base_id, adapter_path = resolve_weights(db, project, req.version_id)
    messages = []
    if req.system_prompt:
        messages.append({"role": "system", "content": req.system_prompt})
    messages.append({"role": "user", "content": req.prompt})
    try:
        engine.ensure_loaded(base_id, adapter_path)
        text = engine.generate(
            messages,
            max_new_tokens=req.max_new_tokens,
            temperature=req.temperature,
            top_p=req.top_p,
        )
    except ModelRuntimeUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"text": text, "base_id": base_id, "adapter_path": adapter_path}
