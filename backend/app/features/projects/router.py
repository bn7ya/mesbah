"""HTTP routes for projects."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, func, select

from ...core.db import get_session
from ...core.models import ModelVersion, Project
from ...core.models import Session as ChatSession
from ...core.models import Task
from . import service
from .schemas import ProjectCreate, ProjectRead, ProjectUpdate

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _to_read(db: Session, project: Project) -> ProjectRead:
    sessions = db.exec(
        select(func.count()).select_from(ChatSession).where(ChatSession.project_id == project.id)
    ).one()
    tasks = db.exec(
        select(func.count()).select_from(Task).where(Task.project_id == project.id)
    ).one()
    versions = db.exec(
        select(func.count()).select_from(ModelVersion).where(ModelVersion.project_id == project.id)
    ).one()
    return ProjectRead(
        **project.model_dump(),
        session_count=sessions,
        task_count=tasks,
        version_count=versions,
    )


@router.get("", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_session)):
    return [_to_read(db, p) for p in service.list_projects(db)]


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(data: ProjectCreate, db: Session = Depends(get_session)):
    project = service.create_project(db, data)
    return _to_read(db, project)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, db: Session = Depends(get_session)):
    project = service.get_project(db, project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return _to_read(db, project)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(project_id: str, data: ProjectUpdate, db: Session = Depends(get_session)):
    project = service.get_project(db, project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    project = service.update_project(db, project, data)
    return _to_read(db, project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, db: Session = Depends(get_session)):
    project = service.get_project(db, project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    service.delete_project(db, project)
