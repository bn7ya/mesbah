"""FastAPI application entry point.

Run from ``backend/`` with::

    uvicorn app.main:app --reload --port 8000

The app boots even when the ML stack (torch/transformers/unsloth) is absent —
those imports are lazy, so the GUI, projects, sessions and the version tree all
work for setup/authoring before any GPU work happens.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .core.db import init_db
from .features.architect.router import router as architect_router
from .features.auto_enhance.router import router as auto_enhance_router
from .features.inference.engine import engine
from .features.inference.router import router as inference_router
from .features.models.router import router as models_router
from .features.projects.router import router as projects_router
from .features.sessions.router import router as sessions_router
from .features.tasks.router import router as tasks_router
from .features.training.router import router as training_router
from .features.versioning.router import router as versioning_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Recover any training run orphaned by a previous worker (uvicorn --reload
    # swap or a crash): its monitor thread died, so the run is stuck "running"
    # even though the subprocess finished. Re-adopt + finalize from status.json.
    from .features.training.manager import manager as training_manager
    training_manager.reconcile_orphans()
    # Loops can't be re-adopted (their worker thread died with the old process):
    # mark any left non-terminal as failed so the UI doesn't show a phantom run.
    from .features.auto_enhance.manager import manager as auto_enhance_manager
    auto_enhance_manager.reconcile_orphans()
    # Pre-resolve the heavy ML imports in the background so the FIRST chat doesn't
    # race the /api/system poll's `import transformers` (which made the first load
    # intermittently fail). Best-effort — boots fine without the ML stack.
    import threading
    threading.Thread(target=engine.warm, daemon=True).start()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (projects_router, tasks_router, sessions_router, models_router,
          inference_router, training_router, versioning_router, auto_enhance_router,
          architect_router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name}


@app.get("/api/system")
def system():
    """Hardware + runtime snapshot for the GUI's status bar."""
    return {
        "gpu_vram_gb": settings.gpu_vram_gb,
        "default_base_model": settings.default_base_model,
        "max_train_seq_len": settings.max_train_seq_len,
        "engine": engine.status(),
    }
