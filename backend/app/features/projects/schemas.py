"""Pydantic I/O schemas for the projects feature."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    # "finetune" (QLoRA on a pretrained base) or "scratch" (custom architecture,
    # random init, full training). For scratch, base_model_repo may be a synthetic
    # family tag like "scratch/qwen3".
    kind: str = "finetune"
    base_model_repo: str
    base_model_local_path: Optional[str] = None
    language: str = "ar"
    # For scratch projects: the ArchitectureSpec (see features/architect/schemas).
    architecture: Optional[dict[str, Any]] = None
    default_train_config: dict[str, Any] = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    active_version_id: Optional[str] = None
    default_train_config: Optional[dict[str, Any]] = None
    language: Optional[str] = None


class ProjectRead(BaseModel):
    id: str
    name: str
    description: str
    kind: str
    base_model_repo: str
    base_model_local_path: Optional[str]
    active_version_id: Optional[str]
    default_train_config: dict[str, Any]
    language: str
    created_at: datetime
    updated_at: datetime

    # convenience counts for the dashboard cards
    session_count: int = 0
    task_count: int = 0
    version_count: int = 0
