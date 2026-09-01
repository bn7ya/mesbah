"""Project configuration package.

Importing the Celery app here means `@shared_task` works from any app
without each one wiring up its own broker connection.
"""
from .celery import app as celery_app

__all__ = ("celery_app",)
