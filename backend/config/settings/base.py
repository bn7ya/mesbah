from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import django_stubs_ext

from mesbah.paths import data_dir

django_stubs_ext.monkeypatch()

BASE_DIR: Path = Path(__file__).resolve().parents[2]


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    raw: str | None = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    raw: str = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


SECRET_KEY: str = env("DJANGO_SECRET_KEY")
DEBUG: bool = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS: list[str] = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS: list[str] = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:4200")

ROOT_URLCONF: str = "config.urls"
WSGI_APPLICATION: str = "config.wsgi.application"
ASGI_APPLICATION: str = "config.asgi.application"
DEFAULT_AUTO_FIELD: str = "django.db.models.BigAutoField"


DJANGO_APPS: list[str] = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
]

THIRD_PARTY_APPS: list[str] = [
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "django_celery_beat",
    "dbs",
]

LOCAL_APPS: list[str] = [
    "apps.common",
    "apps.accounts",
    "apps.datasets",
    "apps.members",
    "apps.models",
    "apps.projects",
    "apps.serving",
    "apps.system",
    "apps.versions",
]

INSTALLED_APPS: list[str] = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE: list[str] = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "dbs.security.middleware.DBSSecurityMiddleware",
]

TEMPLATES: list[dict[str, Any]] = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


DATABASES: dict[str, Any] = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "app"),
        "USER": env("POSTGRES_USER", "app"),
        "PASSWORD": env("POSTGRES_PASSWORD", "app"),
        "HOST": env("POSTGRES_HOST", "db"),
        "PORT": env("POSTGRES_PORT", "5432"),
        # Served over ASGI, so persistent connections give way to psycopg's pool.
        "CONN_MAX_AGE": 0,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {"pool": {"min_size": 1, "max_size": int(env("POSTGRES_POOL_SIZE", "10"))}},
    }
}


REDIS_URL: str = env("REDIS_URL", "redis://redis:6379/0")

CACHES: dict[str, Any] = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

SESSION_ENGINE: str = "django.contrib.sessions.backends.cached_db"


CELERY_BROKER_URL: str = env("CELERY_BROKER_URL", "redis://redis:6379/1")
CELERY_RESULT_BACKEND: str = env("CELERY_RESULT_BACKEND", "redis://redis:6379/2")
CELERY_TASK_SERIALIZER: str = "json"
CELERY_RESULT_SERIALIZER: str = "json"
CELERY_ACCEPT_CONTENT: list[str] = ["json"]
CELERY_TIMEZONE: str = "UTC"
CELERY_TASK_TRACK_STARTED: bool = True
CELERY_TASK_TIME_LIMIT: int = 30 * 60
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP: bool = True
CELERY_TASK_DEFAULT_QUEUE: str = "default"
CELERY_WORKER_PREFETCH_MULTIPLIER: int = 1
CELERY_TASK_ACKS_LATE: bool = True


REST_FRAMEWORK: dict[str, Any] = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.DefaultPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.common.exceptions.exception_handler",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SPECTACULAR_SETTINGS: dict[str, Any] = {
    "TITLE": "Mesbah API",
    "DESCRIPTION": "Mesbah: customize, version and serve language models.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api",
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": False,
    # Several slices have a `role` or a `status`; each set of choices gets its own name.
    "ENUM_NAME_OVERRIDES": {
        "DatasetFormatEnum": "apps.datasets.models.Dataset.Format",
        "DatasetStatusEnum": "apps.datasets.models.Dataset.Status",
        "ExportFormatEnum": "apps.versions.models.Export.Format",
        "MemberRoleEnum": "apps.members.roles.LADDER",
        "MessageRoleEnum": ["system", "user", "assistant"],
        "ModelFamilyEnum": "apps.models.models.HubModel.Family",
        "ModelStatusEnum": "apps.models.models.HubModel.Status",
    },
}


DBS_BACKUP_DIR: str = env("DBS_BACKUP_DIR", "/var/backups/app")
# The `backup` service is the one scheduler. A web worker never takes a backup.
DBS_SCHEDULER: str = "command"
DBS_SCHEDULE_INTERVAL: str = env("DBS_SCHEDULE_INTERVAL", "6h")
DBS_SCHEDULE_KEEP: int = int(env("DBS_SCHEDULE_KEEP", "14"))
DBS_SCHEDULE_KEEP_REMOTE: int = int(env("DBS_SCHEDULE_KEEP_REMOTE", "30"))

DBS_SSH_TARGETS: dict[str, dict[str, str]] = {}

if env("DBS_SSH_HOST"):
    DBS_SSH_TARGETS["offsite"] = {
        "host": env("DBS_SSH_HOST"),
        "username": env("DBS_SSH_USERNAME"),
        "key_filename": env("DBS_SSH_KEY_FILENAME"),
        "remote_dir": env("DBS_SSH_REMOTE_DIR", "/var/backups/app"),
        "known_hosts": env("DBS_SSH_KNOWN_HOSTS", "/root/.ssh/known_hosts"),
    }

DBS_SCHEDULE_PUSH_TARGET: str | None = "offsite" if DBS_SSH_TARGETS else None


LANGUAGE_CODE: str = "en"
TIME_ZONE: str = "UTC"
USE_I18N: bool = True
USE_TZ: bool = True

LANGUAGES: list[tuple[str, str]] = [
    ("en", "English"),
    ("ar", "العربية"),
]
LOCALE_PATHS: list[Path] = [BASE_DIR / "locale"]


STATIC_URL: str = "/static/"
STATIC_ROOT: Path = BASE_DIR / "staticfiles"
MEDIA_URL: str = "/media/"
MEDIA_ROOT: Path = BASE_DIR / "media"

# Models, datasets, version deltas and exports live outside the code, in one directory.
MESBAH_DATA_DIR: Path = data_dir()
# The built Angular app, served by Django itself when Mesbah runs without nginx.
MESBAH_SPA_DIR: Path | None = None
# The built-in engine (ADR-005): `mesbah start` picks both; compose names the `runtime` service.
MESBAH_RUNTIME_URL: str = env("MESBAH_RUNTIME_URL", "http://127.0.0.1:8078")
MESBAH_RUNTIME_TOKEN: str = env("MESBAH_RUNTIME_TOKEN", "")

STORAGES: dict[str, Any] = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}


AUTH_PASSWORD_VALIDATORS: list[dict[str, Any]] = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL: str = "/admin/login/"


LOGGING: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", "INFO")},
    "loggers": {
        "django.db.backends": {"level": "INFO", "propagate": True},
    },
}
