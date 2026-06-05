"""Database engine + session helpers (SQLite via SQLModel).

SQLite is intentional: this is a single-user local studio, not a multi-tenant
service. WAL mode keeps the training subprocess (which writes run status) and the
API process from blocking each other.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session as DBSession
from sqlmodel import SQLModel, create_engine

from .config import settings

# import models so SQLModel.metadata is populated before create_all()
from . import models  # noqa: F401

connect_args = {"check_same_thread": False}
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _record):  # pragma: no cover - infra glue
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.close()


def init_db() -> None:
    settings.ensure_dirs()
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[DBSession]:
    """FastAPI dependency: yields a transactional session."""
    with DBSession(engine) as session:
        yield session
