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


def _ensure_columns() -> None:
    """Add columns that were introduced after a DB was first created.

    ``create_all`` only creates *missing tables* — it never alters an existing
    one, and we have no migration framework (single-user local studio). This
    guard keeps an existing ``misbah.db`` usable without the user dropping data.
    """
    with engine.connect() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(sessions)")}
        if "correction_prompt" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE sessions ADD COLUMN correction_prompt TEXT NOT NULL DEFAULT ''"
            )
            conn.commit()


def init_db() -> None:
    settings.ensure_dirs()
    SQLModel.metadata.create_all(engine)
    _ensure_columns()


def get_session() -> Iterator[DBSession]:
    """FastAPI dependency: yields a request-scoped session.

    ``expire_on_commit=False`` so objects fetched/refreshed earlier in a request
    keep their loaded values after a *later* commit in the same request (e.g. the
    chat route commits the user turn, then the assistant turn — without this the
    user-turn object would be expired and serialize as empty).
    """
    with DBSession(engine, expire_on_commit=False) as session:
        yield session
