"""I/O schemas for sessions, messages and the chat workflow."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

from ...core.models import MessageRole


class SessionCreate(BaseModel):
    title: Optional[str] = None
    task_id: Optional[str] = None
    system_prompt: str = ""
    correction_prompt: str = ""
    model_version_id: Optional[str] = None


class SessionUpdate(BaseModel):
    title: Optional[str] = None
    task_id: Optional[str] = None
    system_prompt: Optional[str] = None
    correction_prompt: Optional[str] = None
    model_version_id: Optional[str] = None


class MessageRead(BaseModel):
    id: str
    session_id: str
    role: MessageRole
    content: str
    original_content: Optional[str]
    corrected: bool
    approved: bool
    include_in_training: bool
    order_index: int
    created_at: datetime
    meta: dict[str, Any]


class SessionRead(BaseModel):
    id: str
    project_id: str
    task_id: Optional[str]
    title: str
    system_prompt: str
    correction_prompt: str = ""
    model_version_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    messages: list[MessageRead] = []
    approved_count: int = 0
    # Which model this chat actually talks to (resolved from model_version_id,
    # falling back to the project's active version).
    model_label: Optional[str] = None
    is_base_model: bool = True


class ChatRequest(BaseModel):
    """Send a user turn and ask the model for a reply."""
    content: str
    max_new_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None


class MessageEdit(BaseModel):
    """Correct an assistant reply and/or change its training flags."""
    content: Optional[str] = None
    approved: Optional[bool] = None
    include_in_training: Optional[bool] = None


class SelfCorrectRequest(BaseModel):
    """Ask the model to improve its own assistant reply (the "magic wand").

    ``correction_prompt`` overrides the session/default correction prompt for
    this one call. Generation knobs fall back to the inference defaults.
    """
    correction_prompt: Optional[str] = None
    max_new_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
