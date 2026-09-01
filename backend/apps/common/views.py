"""Health check.

Deliberately the one endpoint in the project that is public: a probe that
needs credentials cannot tell you the service is up.
"""
from __future__ import annotations

from django.core.cache import cache
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

PROBE_KEY = "health:probe"


class HealthView(APIView):
    """Reports whether the process can reach Postgres and Redis."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary="Service health",
        description="Liveness and dependency check. Public.",
        responses={200: dict, 503: dict},
        auth=[],
    )
    def get(self, request: Request) -> Response:
        checks = {
            "database": self._database(),
            "cache": self._cache(),
        }
        healthy = all(checks.values())
        return Response(
            {"status": "ok" if healthy else "degraded", "checks": checks},
            status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    @staticmethod
    def _database() -> bool:
        try:
            connection.ensure_connection()
        except Exception:
            return False
        return connection.is_usable()

    @staticmethod
    def _cache() -> bool:
        try:
            cache.set(PROBE_KEY, "1", timeout=5)
            return cache.get(PROBE_KEY) == "1"
        except Exception:
            return False
