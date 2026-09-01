"""Celery application.

Broker and result backend come from Django settings under the `CELERY_`
prefix, so there is one configuration source rather than two.
"""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
