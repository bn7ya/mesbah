"""HTTP routes for sessions, the chat workflow and corrections."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from ...core.db import engine as db_engine
from ...core.db import get_session
from ...core.models import Message, MessageRole, ModelVersion, Project
from ...core.models import Session as ChatSession
from ..inference import service as inference_service
from ..inference.engine import ModelRuntimeUnavailable
from . import service
from .schemas import (ChatRequest, MessageEdit, MessageRead, SessionCreate,
                      SessionRead, SessionUpdate)

router = APIRouter(prefix="/api", tags=["sessions"])


def _resolve_version(db: Session, s: ChatSession) -> ModelVersion | None:
    """The version this chat actually uses: the session's, else project active."""
    if s.model_version_id:
        v = db.get(ModelVersion, s.model_version_id)
        if v:
            return v
    project = db.get(Project, s.project_id)
    if project and project.active_version_id:
        return db.get(ModelVersion, project.active_version_id)
    return None


def _session_read(db: Session, s: ChatSession, with_messages: bool = True) -> SessionRead:
    msgs = service.history(db, s.id) if with_messages else []
    version = _resolve_version(db, s)
    return SessionRead(
        **s.model_dump(),
        messages=[MessageRead(**m.model_dump()) for m in msgs],
        approved_count=service.approved_count(db, s.id),
        model_label=version.label if version else None,
        is_base_model=version.is_base if version else True,
    )


# ── session CRUD ──────────────────────────────────────────────────────────────
@router.get("/projects/{project_id}/sessions", response_model=list[SessionRead])
def list_sessions(project_id: str, db: Session = Depends(get_session)):
    stmt = select(ChatSession).where(ChatSession.project_id == project_id).order_by(
        ChatSession.updated_at.desc()
    )
    return [_session_read(db, s, with_messages=False) for s in db.exec(stmt).all()]


@router.post("/projects/{project_id}/sessions", response_model=SessionRead, status_code=201)
def create_session(project_id: str, data: SessionCreate, db: Session = Depends(get_session)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    s = ChatSession(
        project_id=project_id,
        task_id=data.task_id,
        title=data.title or "جلسة جديدة",
        system_prompt=data.system_prompt,
        model_version_id=data.model_version_id or project.active_version_id,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _session_read(db, s)


@router.get("/sessions/{session_id}", response_model=SessionRead)
def get_session_detail(session_id: str, db: Session = Depends(get_session)):
    s = db.get(ChatSession, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    return _session_read(db, s)


@router.patch("/sessions/{session_id}", response_model=SessionRead)
def update_session(session_id: str, data: SessionUpdate, db: Session = Depends(get_session)):
    s = db.get(ChatSession, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    service.touch_session(db, s)
    return _session_read(db, s)


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, db: Session = Depends(get_session)):
    s = db.get(ChatSession, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    for m in db.exec(select(Message).where(Message.session_id == session_id)).all():
        db.delete(m)
    db.delete(s)
    db.commit()


# ── chat ──────────────────────────────────────────────────────────────────────
def _project_and_session(db: Session, session_id: str) -> tuple[Project, ChatSession]:
    s = db.get(ChatSession, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    project = db.get(Project, s.project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project, s


@router.post("/sessions/{session_id}/chat", response_model=list[MessageRead])
def chat(session_id: str, req: ChatRequest, db: Session = Depends(get_session)):
    """Add the user turn, generate the assistant reply, persist both."""
    project, s = _project_and_session(db, session_id)
    hist = service.history(db, session_id)
    user_msg = service.add_message(db, session_id, MessageRole.user, req.content)
    try:
        reply = inference_service.generate_reply(
            db, project, s, hist, req.content,
            max_new_tokens=req.max_new_tokens,
            temperature=req.temperature,
            top_p=req.top_p,
        )
    except ModelRuntimeUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    assistant_msg = service.add_message(db, session_id, MessageRole.assistant, reply)
    service.touch_session(db, s)
    return [MessageRead(**user_msg.model_dump()), MessageRead(**assistant_msg.model_dump())]


@router.post("/sessions/{session_id}/chat/stream")
def chat_stream(session_id: str, req: ChatRequest, db: Session = Depends(get_session)):
    """Stream the assistant reply token-by-token via SSE, then persist it."""
    project, s = _project_and_session(db, session_id)
    hist = service.history(db, session_id)
    user_msg = service.add_message(db, session_id, MessageRole.user, req.content)

    def event_stream():
        yield f"event: user\ndata: {json.dumps({'id': user_msg.id})}\n\n"
        chunks: list[str] = []
        try:
            for chunk in inference_service.stream_reply(
                db, project, s, hist, req.content,
                max_new_tokens=req.max_new_tokens,
                temperature=req.temperature,
                top_p=req.top_p,
            ):
                chunks.append(chunk)
                yield f"event: token\ndata: {json.dumps({'t': chunk})}\n\n"
        except ModelRuntimeUnavailable as exc:
            yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"
            return
        # Persist the assembled reply with a fresh DB session (generator scope).
        from sqlmodel import Session as _S
        with _S(db_engine) as db2:
            msg = service.add_message(db2, session_id, MessageRole.assistant, "".join(chunks))
            s2 = db2.get(ChatSession, session_id)
            if s2:
                service.touch_session(db2, s2)
        yield f"event: done\ndata: {json.dumps({'id': msg.id, 'content': msg.content})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/sessions/{session_id}/regenerate", response_model=MessageRead)
def regenerate(session_id: str, db: Session = Depends(get_session)):
    """Drop the last assistant turn and produce a new one for the same prompt."""
    project, s = _project_and_session(db, session_id)
    msgs = service.history(db, session_id)
    if not msgs or msgs[-1].role != MessageRole.assistant:
        raise HTTPException(400, "Last message is not an assistant reply")
    last_user = next((m for m in reversed(msgs[:-1]) if m.role == MessageRole.user), None)
    if not last_user:
        raise HTTPException(400, "No preceding user message")
    db.delete(msgs[-1])
    db.commit()
    hist = [m for m in msgs[:-1] if m.id != last_user.id]
    try:
        reply = inference_service.generate_reply(db, project, s, hist, last_user.content)
    except ModelRuntimeUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    msg = service.add_message(db, session_id, MessageRole.assistant, reply)
    return MessageRead(**msg.model_dump())


# ── corrections ───────────────────────────────────────────────────────────────
@router.patch("/messages/{message_id}", response_model=MessageRead)
def edit_message(message_id: str, data: MessageEdit, db: Session = Depends(get_session)):
    msg = db.get(Message, message_id)
    if not msg:
        raise HTTPException(404, "Message not found")
    if data.content is not None:
        msg = service.edit_message(db, msg, data.content)
    if data.approved is not None or data.include_in_training is not None:
        msg = service.set_flags(db, msg, approved=data.approved,
                                include_in_training=data.include_in_training)
    return MessageRead(**msg.model_dump())


@router.delete("/messages/{message_id}", status_code=204)
def delete_message(message_id: str, db: Session = Depends(get_session)):
    msg = db.get(Message, message_id)
    if not msg:
        raise HTTPException(404, "Message not found")
    db.delete(msg)
    db.commit()
