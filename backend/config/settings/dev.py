from typing import Any

from django.conf import settings as runtime_settings
from django.http import HttpRequest

from .base import *  # noqa: F403
from .base import INSTALLED_APPS, MIDDLEWARE, env

DEBUG = True

SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-not-a-secret")  # noqa: S105

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [*INSTALLED_APPS, "debug_toolbar"]

MIDDLEWARE = [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    *(m for m in MIDDLEWARE if "whitenoise" not in m),
]


def show_debug_toolbar(request: HttpRequest) -> bool:
    return runtime_settings.DEBUG


DEBUG_TOOLBAR_CONFIG: dict[str, Any] = {"SHOW_TOOLBAR_CALLBACK": show_debug_toolbar}

REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}

EMAIL_BACKEND: str = "django.core.mail.backends.console.EmailBackend"

DBS_BACKUP_PREFIX: str = "dev"

STORAGES = {  # noqa: F405
    **STORAGES,  # noqa: F405
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
