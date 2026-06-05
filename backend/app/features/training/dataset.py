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


def collect_examples(
    db: Session,
    project_id: str,
    *,
    session_ids: Optional[list[str]] = None,
    task_id: Optional[str] = None,
    only_corrected: bool = False,
) -> list[dict[str, Any]]:
    stmt = select(ChatSession).where(ChatSession.project_id == project_id)
    if session_ids:
        stmt = stmt.where(ChatSession.id.in_(session_ids))
    if task_id:
        stmt = stmt.where(ChatSession.task_id == task_id)
    sessions = list(db.exec(stmt).all())

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
            is_target = (
                m.role == MessageRole.assistant
                and m.approved
                and m.include_in_training
                and (m.corrected or not only_corrected)
            )
            if is_target:
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
