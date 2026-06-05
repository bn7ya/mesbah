"""HTTP routes for the model version tree."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from ...core.db import get_session
from ...core.models import ModelVersion, Project
from . import service

router = APIRouter(prefix="/api", tags=["versioning"])


class VersionUpdate(BaseModel):
    label: Optional[str] = None
    notes: Optional[str] = None


@router.get("/projects/{project_id}/versions", response_model=list[ModelVersion])
def list_versions(project_id: str, db: Session = Depends(get_session)):
    return service.list_versions(db, project_id)


@router.get("/projects/{project_id}/version-tree")
def version_tree(project_id: str, db: Session = Depends(get_session)):
    return service.build_tree(db, project_id)


@router.post("/projects/{project_id}/versions/{version_id}/activate", response_model=ModelVersion)
def activate(project_id: str, version_id: str, db: Session = Depends(get_session)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    try:
        return service.set_active(db, project, version_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch("/versions/{version_id}", response_model=ModelVersion)
def update_version(version_id: str, data: VersionUpdate, db: Session = Depends(get_session)):
    version = db.get(ModelVersion, version_id)
    if not version:
        raise HTTPException(404, "Version not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(version, field, value)
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


@router.delete("/versions/{version_id}", status_code=204)
def delete_version(version_id: str, db: Session = Depends(get_session)):
    version = db.get(ModelVersion, version_id)
    if not version:
        raise HTTPException(404, "Version not found")
    try:
        service.delete_version(db, version)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
