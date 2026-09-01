"""One error shape for the whole API.

DRF's default body differs by exception type — sometimes a list, sometimes a
dict, sometimes `{"detail": ...}`. This flattens all of it into one envelope:

    {"error": {"code": "validation_error",
               "message": "Enter a date after today.",
               "fields": {"starts_on": ["Enter a date after today."]}}}
"""
from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)

GENERIC_MESSAGE = "Something went wrong. Try again."


def _flatten(detail: Any) -> str:
    """First human-readable string out of DRF's nested detail structures."""
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        return _flatten(detail[0])
    if isinstance(detail, dict) and detail:
        return _flatten(next(iter(detail.values())))
    return GENERIC_MESSAGE


def exception_handler(exc: Exception, context: dict) -> Response | None:
    response = drf_exception_handler(exc, context)

    if response is None:
        if not isinstance(exc, (Http404, PermissionDenied)):
            logger.exception("Unhandled exception in %s", context.get("view"))
        return None

    detail = response.data
    code = getattr(exc, "default_code", "error")

    fields: dict[str, Any] | None = None
    if isinstance(exc, exceptions.ValidationError) and isinstance(detail, dict):
        fields = detail

    response.data = {
        "error": {
            "code": code,
            "message": _flatten(detail),
            **({"fields": fields} if fields else {}),
        }
    }
    return response
