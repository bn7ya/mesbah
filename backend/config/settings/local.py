from pathlib import Path

from mesbah.database import django_database

from .base import *  # noqa: F403
from .base import MESBAH_DATA_DIR, REST_FRAMEWORK, env, env_bool, env_list

DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY must be set; `mesbah start` sets it.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("MESBAH_ORIGINS", "http://localhost:8077,http://127.0.0.1:8077")

DATABASES = {"default": django_database(env("DATABASE_URL"))}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": str(MESBAH_DATA_DIR / "cache"),
    }
}

_queue: Path = MESBAH_DATA_DIR / "queue"
CELERY_BROKER_URL = "filesystem://"
CELERY_BROKER_TRANSPORT_OPTIONS: dict[str, str | bool] = {
    "data_folder_in": str(_queue / "messages"),
    "data_folder_out": str(_queue / "messages"),
    "control_folder": str(_queue / "control"),
    "store_processed": False,
}
CELERY_RESULT_BACKEND = "cache+memory://"
CELERY_TASK_IGNORE_RESULT: bool = True
for _folder in ("messages", "control"):
    (_queue / _folder).mkdir(parents=True, exist_ok=True)

STATIC_ROOT = MESBAH_DATA_DIR / "static"
MEDIA_ROOT = MESBAH_DATA_DIR / "media"
DBS_BACKUP_DIR = str(MESBAH_DATA_DIR / "backups")
DBS_BACKUP_PREFIX: str = "local"

_spa: str = env("MESBAH_SPA_DIR")
MESBAH_SPA_DIR = Path(_spa) if _spa else None
WHITENOISE_ROOT: str | None = _spa or None

SESSION_COOKIE_HTTPONLY: bool = True
SESSION_COOKIE_SAMESITE: str = "Lax"
CSRF_COOKIE_SAMESITE: str = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF: bool = True
SECURE_REFERRER_POLICY: str = "same-origin"
X_FRAME_OPTIONS: str = "DENY"

REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}
