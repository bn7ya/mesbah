"""Build a QLoRA training dataset from a project's corrected chats.

Strategy: every *approved* assistant turn becomes one SFT example carrying its
full preceding context::

    {"messages": [ {system?}, …prior turns…, {user}, {assistant: corrected} ]}

So a single session with three corrections yields three growing-context
examples. The trainer (``trl`` SFTTrainer) applies the model's chat template and
computes loss on the assistant completion only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from sqlmodel import Session, select

from ...core.models import Message, MessageRole
from ...core.models import Session as ChatSession


def is_target(message: Message, *, only_corrected: bool = False) -> bool:
    """Whether an assistant turn currently qualifies as a training example.

    Shared by the dataset builder and the Data Lab review screen so both agree
    on exactly what "will be used in the next run" means.
    """
    return (
        message.role == MessageRole.assistant
        and message.approved
        and message.include_in_training
        and (message.corrected or not only_corrected)
    )


def _project_sessions(
    db: Session,
    project_id: str,
    *,
    session_ids: Optional[list[str]] = None,
    task_id: Optional[str] = None,
) -> list[ChatSession]:
    stmt = select(ChatSession).where(ChatSession.project_id == project_id)
    if session_ids:
        stmt = stmt.where(ChatSession.id.in_(session_ids))
    if task_id:
        stmt = stmt.where(ChatSession.task_id == task_id)
    return list(db.exec(stmt).all())


def iter_candidates(
    db: Session,
    project_id: str,
    *,
    session_ids: Optional[list[str]] = None,
    task_id: Optional[str] = None,
) -> list[tuple[ChatSession, Message, Optional[str]]]:
    """Every assistant turn in the project, paired with its session and the
    single preceding user turn (for a short, human-readable preview — NOT the
    full growing context ``collect_examples`` builds for actual training)."""
    out: list[tuple[ChatSession, Message, Optional[str]]] = []
    for s in _project_sessions(db, project_id, session_ids=session_ids, task_id=task_id):
        msgs = list(db.exec(
            select(Message).where(Message.session_id == s.id).order_by(Message.order_index)
        ).all())
        last_user: Optional[str] = None
        for m in msgs:
            if m.role == MessageRole.user:
                last_user = m.content
            elif m.role == MessageRole.assistant:
                out.append((s, m, last_user))
    return out


def collect_examples(
    db: Session,
    project_id: str,
    *,
    session_ids: Optional[list[str]] = None,
    task_id: Optional[str] = None,
    only_corrected: bool = False,
) -> list[dict[str, Any]]:
    sessions = _project_sessions(db, project_id, session_ids=session_ids, task_id=task_id)

    examples: list[dict[str, Any]] = []
    for s in sessions:
        msgs = list(db.exec(
            select(Message).where(Message.session_id == s.id).order_by(Message.order_index)
        ).all())
        running: list[dict[str, str]] = []
        if s.system_prompt:
            running.append({"role": "system", "content": s.system_prompt})
        for m in msgs:
            running.append({"role": m.role.value, "content": m.content})
            if is_target(m, only_corrected=only_corrected):
                examples.append({"messages": [dict(x) for x in running]})
    return examples


def write_jsonl(examples: list[dict[str, Any]], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    return len(examples)


def preview(db: Session, project_id: str, limit: int = 10, **kwargs) -> dict[str, Any]:
    examples = collect_examples(db, project_id, **kwargs)
    return {"count": len(examples), "sample": examples[:limit]}
