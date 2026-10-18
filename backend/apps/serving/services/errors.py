from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import APIException


class NoEngine(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = "no_engine"
    default_detail = "No engine is set up to run models."


class ModelNotOnDisk(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "model_not_on_disk"
    default_detail = "The base model isn't downloaded yet."


class BuiltinEngineKept(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "builtin_engine_kept"
    default_detail = "Mesbah's own engine stays. Turn it off instead."


class EngineFailed(APIException):
    status_code: int = status.HTTP_502_BAD_GATEWAY
    default_code: str = "engine_failed"
    default_detail = "The engine couldn't do that."

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(detail or MESSAGES.get(code, str(self.default_detail)), code)
        self.default_code = code
        if code in UNAVAILABLE:
            self.status_code = status.HTTP_503_SERVICE_UNAVAILABLE


UNAVAILABLE: frozenset[str] = frozenset(
    {"engine_unreachable", "engine_timeout", "training_in_progress"}
)
MESSAGES: dict[str, str] = {
    "engine_unreachable": "The engine isn't running.",
    "engine_timeout": "The engine took too long to answer.",
    "engine_rejected_token": "The engine refused Mesbah's token.",
    "training_in_progress": "A training run is using the memory. Chat again when it ends.",
}
