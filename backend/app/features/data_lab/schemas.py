"""I/O schemas for the Data Lab — reviewing and curating training examples."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

ExampleStatus = Literal["pending", "approved", "excluded"]


class DataLabExample(BaseModel):
    """One assistant turn shown in the Data Lab, with a one-exchange preview."""
    id: str
    session_id: str
    session_title: str
    task_id: Optional[str]
    task_title: Optional[str]
    user_content: str
    assistant_content: str
    corrected: bool
    approved: bool
    include_in_training: bool
    status: ExampleStatus
    would_include: bool
    created_at: datetime


class DataLabListResponse(BaseModel):
    items: list[DataLabExample]
    total: int
    page: int
    page_size: int


class DataLabSummary(BaseModel):
    total_candidates: int
    approved_count: int
    included_count: int
    would_include_count: int


class DataLabBulkUpdate(BaseModel):
    message_ids: list[str]
    approved: Optional[bool] = None
    include_in_training: Optional[bool] = None


class DataLabBulkUpdateResult(BaseModel):
    updated: int
