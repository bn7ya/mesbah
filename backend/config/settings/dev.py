"""Development settings.

Served by `runserver` behind the Angular dev-server proxy, so the browser
only ever talks to localhost:4200 — same-origin, no CORS configuration
needed.
"""
from django.conf import settings as runtime_settings

from .base import *  # noqa: F403
from .base import INSTALLED_APPS, MIDDLEWARE, env

DEBUG = True

SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-not-a-secret")  # noqa: S105

ALLOWED_HOSTS = ["*"]

# django-debug-toolbar. Docker gives containers arbitrary IPs, so the usual
# INTERNAL_IPS check is useless here and is replaced with a DEBUG check.
INSTALLED_APPS = [*INSTALLED_APPS, "debug_toolbar"]

# WhiteNoise is a production concern: runserver's staticfiles app already
# serves /static/ in development, and without a collectstatic run WhiteNoise
# warns about the missing directory on every request.
MIDDLEWARE = [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    *(m for m in MIDDLEWARE if "whitenoise" not in m),
]


def show_debug_toolbar(request) -> bool:
    """Show the toolbar only when DEBUG is on, read at request time.

    A test runner may flip `DEBUG = False` after this module is imported, so
    a module-level check would still be True under pytest.
    """
    return runtime_settings.DEBUG


DEBUG_TOOLBAR_CONFIG = {"SHOW_TOOLBAR_CALLBACK": show_debug_toolbar}

# Browsable API, for poking at endpoints without leaving the browser.
REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Uncompressed static files, so a changed file is visible without a rebuild.
STORAGES = {  # noqa: F405
    **STORAGES,  # noqa: F405
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
