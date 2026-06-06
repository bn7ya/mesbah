"""I/O schemas for the auto-enhance loop.

``LoopCreate`` is the launcher payload; every field defaults to the matching
``settings.*`` so an empty request runs sensible defaults. The router resolves
these into ``AutoEnhanceLoop.config`` at create time (frozen → reproducible).
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from ...core.config import settings


class Thresholds(BaseModel):
    """Minimum score (0–10, higher = better) each dimension must reach to pass.

    ``factuality`` is the inverse of hallucination: 10 = no hallucination.
    """
    logic: float = Field(default=7)
    language: float = Field(default=7)
    context: float = Field(default=7)
    factuality: float = Field(default=7)


class LoopCreate(BaseModel):
    name: Optional[str] = None
    generations: int = Field(default_factory=lambda: settings.auto_enhance_generations)
    turns_per_generation: int = Field(
        default_factory=lambda: settings.auto_enhance_turns_per_generation
    )
    thresholds: Thresholds = Field(default_factory=Thresholds)
    max_correction_rounds: int = Field(
        default_factory=lambda: settings.auto_enhance_max_correction_rounds
    )
    topic_source: str = "tasks"            # 'tasks' (seed from project Tasks, else free) | 'free'
    hyperparams: dict[str, Any] = Field(default_factory=dict)
    parent_version_id: Optional[str] = None
    ask_prompt: Optional[str] = None       # None => settings.default_ask_prompt
    eval_prompt: Optional[str] = None       # None => settings.default_eval_prompt
