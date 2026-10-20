from __future__ import annotations

from celery import shared_task

from apps.models.services import DownloadService


@shared_task(name="models.download", ignore_result=True)  # type: ignore[untyped-decorator]
def download_model(model_id: str) -> None:
    DownloadService().run(model_id)
