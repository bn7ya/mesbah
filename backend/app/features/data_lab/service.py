"""Cross-session review and bulk curation of training examples.

Before this feature, the only way to control what a training run actually
learns from was the single approve-star buried inside one chat session, plus
a read-only sample of the first few examples. The Data Lab lists every
candidate assistant turn across the whole project — filterable by task,
session and status — and lets the user bulk include/exclude examples before
a run starts. It reuses the exact same "would this be used?" predicate the
dataset builder uses (``training.dataset.is_target``), so what you see here
always matches what a training run would actually pull in.
"""
from __future__ import annotations

from typing import Optional

from sqlmodel import Session

from ...core.models import Message, Task
from ..training import dataset
from .schemas import (DataLabBulkUpdate, DataLabExample, DataLabListResponse,
                      DataLabSummary, ExampleStatus)


def _status(message: Message) -> ExampleStatus:
    if not message.approved:
        return "pending"
    if not message.include_in_training:
        return "excluded"
    return "approved"


def list_examples(
    db: Session,
    project_id: str,
    *,
    task_id: Optional[str] = None,
    session_id: Optional[str] = None,
    status: Optional[ExampleStatus] = None,
    only_corrected: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> DataLabListResponse:
    session_ids = [session_id] if session_id else None
    rows = dataset.iter_candidates(db, project_id, session_ids=session_ids, task_id=task_id)
    rows.sort(key=lambda r: r[1].created_at, reverse=True)
    if status:
        rows = [r for r in rows if _status(r[1]) == status]

    total = len(rows)
    start = max(page - 1, 0) * page_size
    page_rows = rows[start:start + page_size]

    task_titles: dict[str, str] = {}

    def task_title(tid: Optional[str]) -> Optional[str]:
        if not tid:
            return None
        if tid not in task_titles:
            task = db.get(Task, tid)
            task_titles[tid] = task.title if task else ""
        return task_titles[tid] or None

    items = [
        DataLabExample(
            id=m.id,
            session_id=s.id,
            session_title=s.title,
            task_id=s.task_id,
            task_title=task_title(s.task_id),
            user_content=user_content or "",
            assistant_content=m.content,
            corrected=m.corrected,
            approved=m.approved,
            include_in_training=m.include_in_training,
            status=_status(m),
            would_include=dataset.is_target(m, only_corrected=only_corrected),
            created_at=m.created_at,
        )
        for s, m, user_content in page_rows
    ]
    return DataLabListResponse(items=items, total=total, page=page, page_size=page_size)


def summary(
    db: Session,
    project_id: str,
    *,
    task_id: Optional[str] = None,
    session_id: Optional[str] = None,
    only_corrected: bool = False,
) -> DataLabSummary:
    session_ids = [session_id] if session_id else None
    rows = dataset.iter_candidates(db, project_id, session_ids=session_ids, task_id=task_id)
    messages = [m for _, m, _ in rows]
    return DataLabSummary(
        total_candidates=len(messages),
        approved_count=sum(1 for m in messages if m.approved),
        included_count=sum(1 for m in messages if dataset.is_target(m)),
        would_include_count=sum(
            1 for m in messages if dataset.is_target(m, only_corrected=only_corrected)
        ),
    )


def bulk_update(db: Session, project_id: str, data: DataLabBulkUpdate) -> int:
    """Bulk-set approved/include_in_training, scoped to this project's own
    messages only (a stray id from another project is silently skipped)."""
    if data.approved is None and data.include_in_training is None:
        return 0
    own_ids = {m.id for _, m, _ in dataset.iter_candidates(db, project_id)}
    updated = 0
    for message_id in data.message_ids:
        if message_id not in own_ids:
            continue
        msg = db.get(Message, message_id)
        if not msg:
            continue
        if data.approved is not None:
            msg.approved = data.approved
        if data.include_in_training is not None:
            msg.include_in_training = data.include_in_training
        db.add(msg)
        updated += 1
    if updated:
        db.commit()
    return updated
