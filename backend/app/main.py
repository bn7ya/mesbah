"""FastAPI application entry point.

Run from ``backend/`` with::

    uvicorn app.main:app --reload --port 8000

The app boots even when the ML stack (torch/transformers/unsloth) is absent —
those imports are lazy, so the GUI, projects, sessions and the version tree all
work for setup/authoring before any GPU work happens.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .core.config import BACKEND_DIR, settings
from .core.db import init_db
from .features.architect.router import router as architect_router
from .features.auto_enhance.router import router as auto_enhance_router
from .features.inference.engine import engine
from .features.inference.router import router as inference_router
from .features.models.router import router as models_router
from .features.projects.router import router as projects_router
from .features.sessions.router import router as sessions_router
from .features.settings.router import router as settings_router
from .features.tasks.router import router as tasks_router
from .features.training.router import router as training_router
from .features.versioning.router import router as versioning_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Work around the huggingface_hub 1.x httpx/brotli download crash so model
    # and dataset downloads (and training subprocesses, which set it themselves)
    # don't fail mid-stream. Best-effort; see core/hf_http.py.
    from .core.hf_http import disable_httpx_brotli
    disable_httpx_brotli()
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
          architect_router, settings_router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name}


@app.get("/api/system")
def system():
    """Hardware + runtime snapshot for the GUI's status bar and first-run setup."""
    from .core import hardware
    from .features.settings import service as settings_store
    return {
        **hardware.snapshot(),   # gpus, selected_gpu, gpu_vram_gb, system_ram_gb, cuda_available
        "default_base_model": settings.default_base_model,
        "max_train_seq_len": (settings.max_train_seq_len
                              or hardware.train_defaults("finetune")["max_seq_len"]),
        "onboarded": settings_store.is_onboarded(),
        "engine": engine.status(),
    }


# ── Serve the built Angular SPA (desktop / production) ────────────────────────
# In dev the Angular dev server (:4200) proxies /api here, so this does nothing.
# When a production build exists, FastAPI serves it same-origin so `/api` stays
# relative and the Tauri shell can just point the window at this server.
def _frontend_dist() -> Optional[Path]:
    base = BACKEND_DIR.parent / "frontend" / "dist"
    for candidate in (*sorted(base.glob("*/browser")), base / "browser", base):
        if (candidate / "index.html").is_file():
            return candidate
    return None


_DIST = _frontend_dist()
if _DIST is not None:
    _INDEX = _DIST / "index.html"

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        """Serve built static files; fall back to index.html for SPA client routes."""
        if full_path.startswith("api/"):
            raise HTTPException(404, "Not found")
        candidate = (_DIST / full_path).resolve()
        if candidate.is_file() and str(candidate).startswith(str(_DIST.resolve())):
            return FileResponse(candidate)
        return FileResponse(_INDEX)
