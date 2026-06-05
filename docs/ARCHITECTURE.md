# Architecture

## Processes

```
┌─────────────┐   HTTP /api/*           ┌───────────────────────────┐
│ Angular 20  │ ─────────────────────▶  │ FastAPI (uvicorn :8077)   │
│  (RTL GUI)  │   WS /api/training/..   │  SQLite (WAL)             │
└─────────────┘ ◀───────────────────── │  lazy ML imports          │
      ▲ dev proxy :4200 → :8077         └────────────┬──────────────┘
      │                                              │ spawns
      │                                  ┌────────────▼──────────────┐
      │  live loss curve (WS) ◀──tails── │ train_qlora.py subprocess │
      │                                  │  Unsloth / trl + peft     │
      │                                  │  metrics.jsonl + status   │
      └──────────────────────────────────┴───────────────────────────┘
```

- **One FastAPI process** owns the DB and the resident inference model.
- **Training is a separate subprocess** for clean VRAM teardown and hard cancel.
  It talks back through files: `runs/<id>/metrics.jsonl` (one JSON point per log
  step) and `runs/<id>/status.json` (terminal result). The API tails the metrics
  file over a WebSocket; a monitor thread finalizes the DB on exit.

## Data model (`backend/app/core/models.py`)

```
Project ──< Task
        ──< Session ──< Message        (Message.corrected/approved = training signal)
        ──< TrainingRun ──> ModelVersion (adapter_path; parent_id = version tree)
```

Circular foreign keys (project↔active_version, version self-parent, run↔version)
mean we **don't** use ORM relationships; services query explicitly and delete with
`PRAGMA defer_foreign_keys` + reference-nulling.

## Request → training → version, end to end

1. **Chat** `POST /api/sessions/{id}/chat` → inference engine loads base (4-bit) +
   active LoRA adapter → reply persisted.
2. **Correct** `PATCH /api/messages/{id}` `{content}` → original draft preserved,
   `corrected=approved=true`.
3. **Dataset** the training feature collects every approved assistant turn with its
   preceding context into `{messages:[…]}` JSONL.
4. **Run** `POST /api/projects/{id}/training/runs` → prepare dataset + config.json →
   `manager.launch()` unloads inference, spawns `train_qlora.py`.
5. **Live** GUI opens the run WebSocket; loss/lr/VRAM stream in.
6. **Version** on success a `ModelVersion` node is appended under the parent and
   auto-activated → next chat uses the new adapter.

## Frontend shape (`frontend/src/app`)

- `core/api.ts` — one typed gateway; `core/types.ts` — mirrors backend schemas.
- `app.ts` — glass shell (brand, GPU/VRAM status, toast, confirm).
- `features/{projects,workspace,chat,tasks,training,versions}` — standalone,
  signal-based components; the workspace hosts the four panels in PrimeNG tabs.

See per-feature `CLAUDE.md` files for the details of each slice.
