from __future__ import annotations

from typing import Any
from urllib.parse import SplitResult, parse_qs, unquote, urlsplit

DEFAULT_PORT: int = 5432
POOL_SIZE: int = 10


def django_database(url: str) -> dict[str, Any]:
    parts: SplitResult = urlsplit(url)
    if parts.scheme not in {"postgres", "postgresql"}:
        raise ValueError(f"Mesbah needs PostgreSQL, not {parts.scheme or 'an empty URL'}.")
    query: dict[str, list[str]] = parse_qs(parts.query)
    host: str = query.get("host", [parts.hostname or "localhost"])[0]
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parts.path.lstrip("/")) or "postgres",
        "USER": unquote(parts.username or ""),
        "PASSWORD": unquote(parts.password or ""),
        "HOST": host,
        "PORT": str(parts.port or DEFAULT_PORT),
        "CONN_MAX_AGE": 0,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {"pool": {"min_size": 1, "max_size": POOL_SIZE}},
    }
