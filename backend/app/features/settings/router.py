"""HTTP routes for persisted app settings (onboarding, GPU choice, theme, tokens)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from . import service

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsPatch(BaseModel):
    selected_gpu_index: Optional[int] = None
    gpu_vram_gb_override: Optional[float] = None
    theme: Optional[str] = None
    # {name: secret} — empty/null secret removes that token. Never echoed back raw.
    tokens: Optional[dict[str, Optional[str]]] = None


class OnboardRequest(BaseModel):
    selected_gpu_index: Optional[int] = None


@router.get("")
def get_settings():
    """User settings with token secrets masked to hints."""
    return service.public()


@router.patch("")
def patch_settings(req: SettingsPatch):
    # exclude_unset keeps PATCH semantics: only forward keys the caller actually set.
    return service.patch(req.model_dump(exclude_unset=True))


@router.post("/onboard")
def onboard(req: OnboardRequest):
    """Finish first-run setup: persist the chosen GPU and mark the app onboarded."""
    return service.onboard(req.selected_gpu_index)
