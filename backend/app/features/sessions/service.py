"""Session + message logic, including the correction workflow.

The correction loop is the product's whole reason for existing:

    user asks → model answers → user *edits* the answer → the edited turn
    becomes a training example.

``edit_message`` captures the model's original draft the first time a reply is
touched, so a future view can show "before vs after" and so the dataset builder
can prefer the corrected text.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, func, select

from ...core.models import Message, MessageRole, Project
from ...core.models import Session as ChatSession
from ...core.think import join_think, split_think


def _now() -> datetime:
    return datetime.now(timezone.utc)


def next_order_index(db: Session, session_id: str) -> int:
    current = db.exec(
        select(func.max(Message.order_index)).where(Message.session_id == session_id)
    ).one()
    return (current or 0) + 1 if current is not None else 0


def history(db: Session, session_id: str) -> list[Message]:
    stmt = select(Message).where(Message.session_id == session_id).order_by(Message.order_index)
    return list(db.exec(stmt).all())


def add_message(db: Session, session_id: str, role: MessageRole, content: str,
                approved: bool = False) -> Message:
    msg = Message(
        session_id=session_id,
        role=role,
        content=content,
        order_index=next_order_index(db, session_id),
        approved=approved,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def touch_session(db: Session, session: ChatSession) -> None:
    session.updated_at = _now()
    db.add(session)
    db.commit()


def edit_message(db: Session, message: Message, new_content: str) -> Message:
    """Apply a correction to an assistant reply.

    Preserves the first-seen draft in ``original_content`` and flips
    ``corrected``. Editing also auto-approves: a human bothered to fix it, so it
    is, by definition, the target the model should learn.

    Thinking models: if the reply carried a ``<think>…</think>`` chain and the
    correction dropped it, the previous chain is re-attached — a training example
    without it teaches the fine-tuned model to stop thinking. An explicit (even
    empty) ``<think></think>`` in the new content is respected as deliberate.
    """
    if message.role == MessageRole.assistant:
        prev_thinking, _ = split_think(message.content)
        new_thinking, new_answer = split_think(new_content)
        if prev_thinking is not None and new_thinking is None:
            new_content = join_think(prev_thinking, new_answer)
    if message.role == MessageRole.assistant and message.original_content is None:
        message.original_content = message.content
    if message.content != new_content:
        message.content = new_content
        if message.role == MessageRole.assistant:
            message.corrected = True
            message.approved = True
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def apply_self_correction(db: Session, message: Message, improved: str,
                          correction_prompt: str) -> Message:
    """Persist a model-generated self-correction of an assistant reply.

    Like :func:`edit_message` it preserves the first draft in
    ``original_content`` and flips ``corrected``. Unlike it, it deliberately
    does **not** touch ``approved``: a self-correction is the model's own
    rewrite, not a human signal of quality, so it stays pending human review
    before it can become a training example. Provenance is recorded in ``meta``.
    """
    if message.original_content is None:
        message.original_content = message.content
    message.content = improved
    message.corrected = True
    # Reassign a NEW dict so SQLAlchemy detects the JSON column change.
    meta = dict(message.meta or {})
    meta["self_corrected"] = True
    meta["correction_prompt"] = correction_prompt
    meta["corrected_at"] = _now().isoformat()
    message.meta = meta
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def set_flags(db: Session, message: Message, *, approved: bool | None,
              include_in_training: bool | None) -> Message:
    if approved is not None:
        message.approved = approved
    if include_in_training is not None:
        message.include_in_training = include_in_training
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def import_sessions(db: Session, target_project_id: str, session_ids: list[str]) -> list[ChatSession]:
    """Copy whole chats (with their messages + corrections) into another project.

    Each imported session becomes a fresh session in the target project, bound to
    the target's active model version (the source version doesn't exist here).
    Message correction/approval flags are preserved so the imported turns are
    immediately usable as training data in the new project.
    """
    target = db.get(Project, target_project_id)
    if not target:
        raise ValueError("Target project not found")

    created: list[ChatSession] = []
    for sid in session_ids:
        src = db.get(ChatSession, sid)
        if not src or src.project_id == target_project_id:
            continue  # skip missing or same-project sessions
        new_session = ChatSession(
            project_id=target_project_id,
            task_id=None,
            title=f"{src.title} (مستورد)",
            system_prompt=src.system_prompt,
            model_version_id=target.active_version_id,
        )
        db.add(new_session)
        db.flush()  # assign id
        src_msgs = db.exec(
            select(Message).where(Message.session_id == src.id).order_by(Message.order_index)
        ).all()
        for m in src_msgs:
            db.add(Message(
                session_id=new_session.id,
                role=m.role,
                content=m.content,
                original_content=m.original_content,
                corrected=m.corrected,
                approved=m.approved,
                include_in_training=m.include_in_training,
                order_index=m.order_index,
                meta=m.meta,
            ))
        created.append(new_session)
    db.commit()
    for s in created:
        db.refresh(s)
    return created


def approved_count(db: Session, session_id: str) -> int:
    return db.exec(
        select(func.count()).select_from(Message).where(
            Message.session_id == session_id,
            Message.role == MessageRole.assistant,
            Message.approved == True,  # noqa: E712
            Message.include_in_training == True,  # noqa: E712
        )
    ).one()
