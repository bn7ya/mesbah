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


# Columns introduced *after* a table's first release. ``create_all`` only
# creates missing *tables* — it never alters an existing one, and we have no
# migration framework (single-user local studio). Each entry is
# ``(table, column, DDL fragment)``; the fragment must carry a DEFAULT because
# SQLite cannot add a NOT NULL column to a table that already has rows without
# one. Append a line here whenever you add a column to ``core/models.py``.
_ADDED_COLUMNS: list[tuple[str, str, str]] = [
    ("sessions", "correction_prompt", "TEXT NOT NULL DEFAULT ''"),
    ("projects", "kind", "TEXT NOT NULL DEFAULT 'finetune'"),
]


def _ensure_columns() -> None:
    """Bring an existing ``misbah.db`` up to the current model shape.

    Adds any column from :data:`_ADDED_COLUMNS` that a pre-existing table is
    missing, so an older DB keeps working without the user dropping data.
    """
    with engine.connect() as conn:
        for table, column, ddl in _ADDED_COLUMNS:
            existing = {row[1] for row in
                        conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            if not existing:
                continue  # table doesn't exist yet — create_all will make it
            if column not in existing:
                conn.exec_driver_sql(
                    f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        # Index for the (post-hoc) projects.kind column; harmless if it exists.
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_projects_kind ON projects (kind)")
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
