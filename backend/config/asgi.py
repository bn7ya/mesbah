"""ASGI entry point.

Nothing serves this today — dev runs `runserver`, prod runs gunicorn against
`wsgi.py`. Django Channels + a Redis channel layer get wired in here once
`apps/training` is ported and needs its live-metrics WebSocket (see the root
migration plan and apps/common/CLAUDE.md) — this file is what changes then.
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_asgi_application()
