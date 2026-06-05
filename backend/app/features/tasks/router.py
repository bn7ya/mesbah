"""HTTP routes for tasks — objectives the model should learn within a project."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from ...core.db import get_session
from ...core.models import Task, TaskStatus

router = APIRouter(prefix="/api/projects/{project_id}/tasks", tags=["tasks"])


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    objective: str = ""
    status: TaskStatus = TaskStatus.todo


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    objective: Optional[str] = None
    status: Optional[TaskStatus] = None
    order_index: Optional[int] = None


@router.get("", response_model=list[Task])
def list_tasks(project_id: str, db: Session = Depends(get_session)):
    stmt = select(Task).where(Task.project_id == project_id).order_by(Task.order_index, Task.created_at)
    return list(db.exec(stmt).all())


@router.post("", response_model=Task, status_code=status.HTTP_201_CREATED)
def create_task(project_id: str, data: TaskCreate, db: Session = Depends(get_session)):
    task = Task(project_id=project_id, **data.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.patch("/{task_id}", response_model=Task)
def update_task(project_id: str, task_id: str, data: TaskUpdate, db: Session = Depends(get_session)):
    task = db.get(Task, task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    task.updated_at = datetime.now(timezone.utc)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(project_id: str, task_id: str, db: Session = Depends(get_session)):
    task = db.get(Task, task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    db.delete(task)
    db.commit()
