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

from ...core.models import Message, MessageRole
from ...core.models import Session as ChatSession


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
    """
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


def approved_count(db: Session, session_id: str) -> int:
    return db.exec(
        select(func.count()).select_from(Message).where(
            Message.session_id == session_id,
            Message.role == MessageRole.assistant,
            Message.approved == True,  # noqa: E712
            Message.include_in_training == True,  # noqa: E712
        )
    ).one()
