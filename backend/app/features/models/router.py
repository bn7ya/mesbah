"""HTTP routes for model discovery + downloads."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from . import service

router = APIRouter(prefix="/api/models", tags=["models"])


class DownloadRequest(BaseModel):
    repo_id: str


@router.get("/curated")
def curated():
    """Recommended base models for the new-project picker."""
    return service.CURATED_MODELS


@router.get("/search")
def search(query: str, limit: int = 20):
    return service.search(query, limit)


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
