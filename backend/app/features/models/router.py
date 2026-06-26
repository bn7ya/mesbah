"""HTTP routes for model discovery + downloads."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import service

router = APIRouter(prefix="/api/models", tags=["models"])


class DownloadRequest(BaseModel):
    repo_id: str


class HfTokenRequest(BaseModel):
    token: str


@router.get("/hf-token")
def hf_token_status():
    """Whether a HuggingFace token is configured (never returns the secret)."""
    return service.hf_token_status()


@router.post("/hf-token")
def set_hf_token(req: HfTokenRequest):
    """Validate against the Hub, then persist + apply the token. 400 if invalid."""
    try:
        return service.set_hf_token(req.token)
    except Exception as exc:  # noqa: BLE001 — surface a clean validation error
        msg = str(exc)
        if "401" in msg or "invalid" in msg.lower() or "unauthorized" in msg.lower():
            raise HTTPException(400, "Invalid HuggingFace token — check it and retry.")
        raise HTTPException(400, f"Could not set token: {msg}")


@router.delete("/hf-token")
def clear_hf_token():
    """Remove a GUI-set token (reverts to the environment value, if any)."""
    return service.clear_hf_token()


@router.get("/curated")
def curated():
    """Recommended base models for the new-project picker."""
    return service.CURATED_MODELS


@router.get("/search")
def search(query: str, limit: int = 20):
    return service.search(query, limit)


@router.get("/datasets/search")
def search_datasets(query: str, limit: int = 20):
    """Search HuggingFace datasets (the training-corpus picker)."""
    return service.search_datasets(query, limit)


@router.get("/datasets/preview")
def dataset_preview(repo_id: str, config: str | None = None, split: str | None = None):
    """List a dataset's columns so the UI can pick a text field."""
    return service.dataset_preview(repo_id, config, split)


@router.get("/inspect")
def inspect(repo_id: str):
    """Architecture facts from a model's config.json (e.g. an embedding source)."""
    try:
        return service.inspect_model(repo_id)
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        if "404" in msg or "not found" in msg or "entrynotfound" in msg or "repositorynotfound" in msg:
            raise HTTPException(404, f"Could not read config.json for '{repo_id}': {exc}")
        if "401" in msg or "403" in msg or "gated" in msg or "authentication" in msg:
            raise HTTPException(403, f"'{repo_id}' is private/gated — set MISBAH_HF_TOKEN: {exc}")
        raise HTTPException(502, f"Failed to inspect '{repo_id}': {exc}")


@router.get("/local")
def local():
    return service.list_local()


@router.post("/download")
def download(req: DownloadRequest):
    dl = service.manager.start(req.repo_id)
    return service.manager.status(dl.repo_id)


@router.get("/download/status")
def download_status(repo_id: str):
    return service.manager.status(repo_id)
