from __future__ import annotations

from celery import shared_task
from django.contrib.auth.models import AnonymousUser

from apps.versions.services import ExportService

DAY_SECONDS: int = 24 * 3600


@shared_task(name="versions.package", ignore_result=True)  # type: ignore[untyped-decorator]
def package(export_id: str) -> None:
    ExportService(AnonymousUser()).run(export_id)


# Merging loads the whole model, so it takes the trainer's slot instead of running beside it.
@shared_task(  # type: ignore[untyped-decorator]
    name="versions.convert", queue="heavy", ignore_result=True, time_limit=DAY_SECONDS
)
def convert(export_id: str) -> None:
    ExportService(AnonymousUser()).run(export_id)
