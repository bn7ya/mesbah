"""HTTP routes for the Data Lab — review + bulk curation of training examples."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ...core.db import get_session
from ...core.models import Project
from . import service
from .schemas import (DataLabBulkUpdate, DataLabBulkUpdateResult,
                      DataLabListResponse, DataLabSummary, ExampleStatus)

router = APIRouter(prefix="/api/projects/{project_id}/data-lab", tags=["data-lab"])


def _require_project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.get("/examples", response_model=DataLabListResponse)
def list_examples(
    project_id: str,
    task_id: Optional[str] = None,
    session_id: Optional[str] = None,
    status: Optional[ExampleStatus] = None,
    only_corrected: bool = False,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_session),
):
    _require_project(db, project_id)
    return service.list_examples(
        db, project_id, task_id=task_id, session_id=session_id, status=status,
        only_corrected=only_corrected, page=page, page_size=page_size,
    )


@router.get("/summary", response_model=DataLabSummary)
def get_summary(
    project_id: str,
    task_id: Optional[str] = None,
    session_id: Optional[str] = None,
    only_corrected: bool = False,
    db: Session = Depends(get_session),
):
    _require_project(db, project_id)
    return service.summary(
        db, project_id, task_id=task_id, session_id=session_id, only_corrected=only_corrected,
    )


@router.patch("/examples", response_model=DataLabBulkUpdateResult)
def bulk_update(project_id: str, data: DataLabBulkUpdate, db: Session = Depends(get_session)):
    _require_project(db, project_id)
    updated = service.bulk_update(db, project_id, data)
    return DataLabBulkUpdateResult(updated=updated)
