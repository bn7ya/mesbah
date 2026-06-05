"""Inference orchestration: resolve which weights to use, then generate.

Resolves a (project, version) pair into a concrete ``(base_id, adapter_path)``
and drives :data:`engine`. ``base_id`` prefers a local download so we never hit
the network at chat time.
"""
from __future__ import annotations

from typing import Any, Iterator, Optional

from sqlmodel import Session

from ...core.models import Message, ModelVersion, Project
from ...core.models import Session as ChatSession
from .engine import engine


def resolve_weights(db: Session, project: Project, version_id: Optional[str]) -> tuple[str, Optional[str]]:
    """Return ``(base_id, adapter_path)`` for the requested version.

    ``version_id`` falls back to the project's active version, then to the base
    model with no adapter.
    """
    base_id = project.base_model_local_path or project.base_model_repo
    vid = version_id or project.active_version_id
    adapter_path: Optional[str] = None
    if vid:
        version = db.get(ModelVersion, vid)
        if version and not version.is_base:
            adapter_path = version.adapter_path
    return base_id, adapter_path


def build_messages(session: ChatSession, history: list[Message], user_text: str) -> list[dict[str, str]]:
    msgs: list[dict[str, str]] = []
    if session.system_prompt:
        msgs.append({"role": "system", "content": session.system_prompt})
    for m in history:
        msgs.append({"role": m.role.value, "content": m.content})
    msgs.append({"role": "user", "content": user_text})
    return msgs


def generate_reply(
    db: Session,
    project: Project,
    session: ChatSession,
    history: list[Message],
    user_text: str,
    **gen_kwargs: Any,
) -> str:
    base_id, adapter_path = resolve_weights(db, project, session.model_version_id)
    engine.ensure_loaded(base_id, adapter_path)
    messages = build_messages(session, history, user_text)
    return engine.generate(messages, **gen_kwargs)


def stream_reply(
    db: Session,
    project: Project,
    session: ChatSession,
    history: list[Message],
    user_text: str,
    **gen_kwargs: Any,
) -> Iterator[str]:
    base_id, adapter_path = resolve_weights(db, project, session.model_version_id)
    engine.ensure_loaded(base_id, adapter_path)
    messages = build_messages(session, history, user_text)
    yield from engine.stream(messages, **gen_kwargs)
