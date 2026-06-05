# backend/ — FastAPI + QLoRA engine

Python 3.13, FastAPI, SQLModel/SQLite. Runs in the conda env that already has
`torch 2.11.0+cu130`.

## Run / verify

```bash
pip install -r requirements.txt        # API layer (lets the app boot)
pip install -r requirements-ml.txt     # ML stack (chat + training)
uvicorn app.main:app --port 8077       # 8000 is usually taken by Django
```

The app **boots without the ML stack** — `torch`/`transformers`/`unsloth` are
imported lazily. Endpoints that need the GPU return **503** with guidance until
`requirements-ml.txt` is installed.

## Shape

```
app/
  main.py            FastAPI wiring (includes every feature router) + /api/health, /api/system
  core/
    config.py        Settings (env prefix MISBAH_) + data-dir layout
    db.py            SQLite engine (WAL), init_db(), get_session() dependency
    models.py        ALL SQLModel tables (one place — see "Data rules")
    events.py        async pub/sub for live progress (currently the WS tails files)
  features/<name>/   router.py + service.py (+ schemas.py); each has a CLAUDE.md
  scripts/
    train_qlora.py   standalone training subprocess (imports nothing from app)
    download_model.py
  data/              models/ adapters/ datasets/ runs/ hf_cache/ misbah.db  (git-ignored)
```

## Data rules (important)

- **All tables live in `core/models.py`.** Foreign keys are circular
  (project↔active_version, version self-parent, run↔version), and with
  `from __future__ import annotations` SQLModel `Relationship` breaks the mapper —
  so we **do not** declare ORM relationships. Access via explicit `select(...)`.
- **Cascade deletes are manual**, in the services, using
  `db.connection().exec_driver_sql("PRAGMA defer_foreign_keys=ON")` plus
  nulling incoming references and `db.flush()` before the delete. See
  `features/projects/service.py::delete_project` and
  `features/versioning/service.py::delete_version` for the pattern — copy it.

## Feature pattern

Each feature is `router.py` (HTTP/WS) + `service.py` (logic) [+ `schemas.py`].
Routers depend on `get_session`; services take a `Session` and the domain objects.
Keep ML imports lazy and inside the feature that needs them
(`inference/engine.py`, `training/manager.py` → subprocess).

## Conventions

- Pydantic/SQLModel everywhere; return models or typed schemas, never raw dicts.
- Keep technical terms English; user-facing strings live in the frontend.
- New feature → new folder under `features/`, add its router to `main.py`, write
  its `CLAUDE.md`.
