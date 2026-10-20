from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpRequest


def index(request: HttpRequest) -> FileResponse:
    root: Path | None = settings.MESBAH_SPA_DIR
    if root is None:
        raise Http404
    response: FileResponse = FileResponse(
        (root / "index.html").open("rb"), content_type="text/html"
    )
    response["Cache-Control"] = "no-store"
    return response
