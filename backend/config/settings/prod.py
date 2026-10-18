from .base import *  # noqa: F403
from .base import env, env_bool

DEBUG = False

if not env("DJANGO_SECRET_KEY"):
    raise RuntimeError("DJANGO_SECRET_KEY must be set in production.")

if not ALLOWED_HOSTS:  # noqa: F405
    raise RuntimeError("DJANGO_ALLOWED_HOSTS must be set in production.")


SECURE_PROXY_SSL_HEADER: tuple[str, str] = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST: bool = True

SECURE_SSL_REDIRECT: bool = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
SESSION_COOKIE_SECURE: bool = env_bool("DJANGO_SECURE_COOKIES", False)
CSRF_COOKIE_SECURE: bool = env_bool("DJANGO_SECURE_COOKIES", False)

SECURE_HSTS_SECONDS: int = int(env("DJANGO_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS: bool = True
SECURE_HSTS_PRELOAD: bool = True

SECURE_CONTENT_TYPE_NOSNIFF: bool = True
SECURE_REFERRER_POLICY: str = "same-origin"
X_FRAME_OPTIONS: str = "DENY"

SESSION_COOKIE_HTTPONLY: bool = True
SESSION_COOKIE_SAMESITE: str = "Lax"
CSRF_COOKIE_SAMESITE: str = "Lax"

# The backup panel's session guard scores the client's network, and nginx is the
# proxy in front of gunicorn. Count one more for each proxy in front of nginx.
DBS_TRUST_FORWARDED_FOR: bool = True
DBS_TRUSTED_PROXIES: int = int(env("DBS_TRUSTED_PROXIES", "1"))

DBS_BACKUP_PREFIX: str = "prod"


EMAIL_BACKEND: str = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST: str = env("EMAIL_HOST", "")
EMAIL_PORT: int = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER: str = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD: str = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS: bool = True
DEFAULT_FROM_EMAIL: str = env("DEFAULT_FROM_EMAIL", "no-reply@example.com")


REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}
