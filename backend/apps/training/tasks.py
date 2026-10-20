from __future__ import annotations

from celery import shared_task

from apps.training.services import RunnerService

WEEK_SECONDS: int = 7 * 24 * 3600


# One trainer at a time: the `heavy` queue has one worker with one slot.
@shared_task(  # type: ignore[untyped-decorator]
    name="training.run", queue="heavy", ignore_result=True, time_limit=WEEK_SECONDS
)
def train(run_id: str) -> None:
    RunnerService().run(run_id)
