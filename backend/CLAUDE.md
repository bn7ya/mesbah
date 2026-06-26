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
  main.py            FastAPI wiring (includes every feature router) + /api/health, /api/system;
                     also serves the built Angular SPA (frontend/dist) when present, with an
                     index.html SPA fallback — desktop/prod runs same-origin (dev uses the proxy).
  core/
    config.py        Settings (env prefix MISBAH_) + data-dir layout. Hardware fields
                     (gpu_vram_gb/host_ram_gb/max_train_seq_len) are env OVERRIDES only
                     (default None) — use resolved_vram_gb()/resolved_ram_gb().
    hardware.py      Detect GPUs (pynvml→torch→nvidia-smi) + RAM; pick the effective GPU
                     (user choice via features/settings); compute_train_defaults(vram,ram)
                     derives seq-len/batch/grad-accum/lora_r/offload from real hardware.
    db.py            SQLite engine (WAL), init_db(), get_session() dependency
    models.py        ALL SQLModel tables (one place — see "Data rules")
    events.py        async pub/sub for live progress (currently the WS tails files)
  features/<name>/   router.py + service.py (+ schemas.py); each has a CLAUDE.md.
                     settings/ holds the GUI-set app settings (onboarding, GPU choice,
                     theme, generic API tokens) in data/app_settings.json.
  scripts/
    train_qlora.py   standalone QLoRA fine-tuning subprocess (kind="finetune")
    train_scratch.py standalone from-scratch full-training subprocess (kind="scratch")
    download_model.py
  data/              models/ adapters/ datasets/ runs/ hf_cache/ projects/ misbah.db  (git-ignored)
```

## Per-project storage (`data/projects/<id>/`)

A project of either kind owns a self-contained folder created on `create_project`
and removed on `delete_project`:

```
projects/<id>/
  versions/<run_id>/   trained checkpoint for each run (→ ModelVersion.adapter_path)
  data/<run_id>.jsonl  the training corpus/dataset used
  offload/<run_id>/    paging spillover for that run
  metadata.json        model metadata (kind, base/arch spec, train config)
```

Big base-model weights stay in the **shared** `models_dir`/`hf_home` cache (not
copied per project). Transient run logs (`config.json`, `metrics.jsonl`,
`status.json`, `train.log`) stay under `runs/<run_id>/` because the WebSocket and
crash-recovery look runs up by `run_id` alone — keep that contract. See
`core/config.py` (`project_*` helpers) and `features/projects/service.py`.

## Project kinds

`Project.kind` is `"finetune"` (QLoRA on a pretrained base) or `"scratch"` (a
custom architecture, random-initialised, fully trained). The training manager
picks the subprocess by kind; the architecture spec lives in
`default_train_config["architecture"]` and `metadata.json`. The `architect`
feature estimates params/memory before creation (pure-Python, no torch).

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
