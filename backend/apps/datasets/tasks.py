from __future__ import annotations

from celery import shared_task

from apps.datasets.services import ImportService


@shared_task(name="datasets.import", ignore_result=True)  # type: ignore[untyped-decorator]
def import_dataset(dataset_id: str) -> None:
    ImportService().run(dataset_id)
