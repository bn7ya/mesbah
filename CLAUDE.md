# مِصباح · Misbah — LLM Fine-tuning Studio

A local, single-user studio for fine-tuning an 8–16B LLM into a great **Arabic
long-context assistant** via **QLoRA**, driven entirely from a glassy RTL GUI.
You chat with the model, **correct** its answers, and those corrections become
training data. Each fine-tune appends a node to a **version tree** you can
branch, activate (rollback), and keep enhancing.

> The UI is **Arabic, RTL**. Technical terms (QLoRA, LoRA, adapter, base model,
> loss, VRAM, …) stay in **English** everywhere — UI labels and code alike.

## The product in one diagram

```
Project (wraps one HuggingFace base model)
├── Task            objective the model should learn
├── Session (chat)  ── Message ── (user edits assistant reply = correction)
└── TrainingRun ──▶ ModelVersion        ← node in the version tree
                     (QLoRA adapter)        branch · activate(rollback) · enhance
```

## Stack

| Layer    | Tech |
|----------|------|
| Frontend | Angular 20 (standalone, signals) + PrimeNG 20 + `@primeuix/themes` (Aura), **Tailwind v4**, RTL, minimal/Notion-like, chart.js |
| Backend  | FastAPI + SQLModel/SQLite, WebSocket live metrics (+ live trainer logs); serves the built SPA in prod/desktop |
| Training | QLoRA via **Unsloth** (preferred) or transformers + peft + trl + bitsandbytes; runs as an isolated subprocess |
| Model    | **Qwen/Qwen3-14B** (default) — see `docs/MODEL_SELECTION.md` |
| Hardware | **Auto-detected** GPU/VRAM/RAM (pynvml → torch → nvidia-smi); training params derive from the real card, GPU chosen on first run. Dev box: RTX 5080 16 GB, sm_120, CUDA 13.2, torch 2.11+cu130 — see `docs/HARDWARE.md` |
| Desktop  | Optional **Tauri** shell (`frontend/src-tauri`) — launches the local backend, opens the studio; `.deb`/`.AppImage` (Linux), `.msi`/`.exe` (Windows) |

## Layout

```
backend/   FastAPI app — see backend/CLAUDE.md
  app/core/        config, db, models (all SQLModel tables), events (live pub/sub)
  app/features/*/  one folder per feature, each with its own CLAUDE.md
  scripts/         train_qlora.py (subprocess), download_model.py
frontend/  Angular app — see frontend/CLAUDE.md
  src/app/core/        api gateway + types
  src/app/features/*/  one folder per feature, each with its own CLAUDE.md
docs/      ARCHITECTURE.md · MODEL_SELECTION.md · HARDWARE.md
```

## Run it

```bash
# 1) Backend (uses the conda env that already has torch 2.11+cu130)
cd backend
pip install -r requirements.txt          # API layer — boots instantly
pip install -r requirements-ml.txt       # ML/QLoRA stack — needed for chat & training
python scripts/download_model.py Qwen/Qwen3-14B   # ~28 GB, one-time
uvicorn app.main:app --port 8077

# 2) Frontend (separate terminal)
cd frontend
npm install
npm start                                 # http://localhost:4200  (proxies /api → :8077)
```

The API **boots without the ML stack** (heavy imports are lazy), so the GUI,
projects, sessions and version tree all work for authoring before any GPU work.
Chat/training return a clear 503/“not installed” until `requirements-ml.txt` is in.

## Conventions

- **Feature folders own behaviour; `core/models.py` owns the data shape.** We do
  not use SQLModel `Relationship` (circular FKs + `from __future__ import
  annotations` break the mapper) — query explicitly and cascade-delete in
  services with `PRAGMA defer_foreign_keys`.
- **Lazy ML imports** in `features/inference/engine.py` and `scripts/train_qlora.py`.
- **One model resident at a time** on 16 GB; training unloads the inference engine first.
- **Arabic UI, English technical terms.** Don't translate `loss`, `adapter`, etc.
- Each feature directory has a **`CLAUDE.md`** — read it before changing that feature.

## Verify

`backend/`: the smoke flow (project → task → session → correction → dataset →
run prep → version tree → cascade delete) is the canonical end-to-end check.
`frontend/`: `npm run build` must be warning-clean; the running app is verified
against a live backend through the dev proxy.
