from __future__ import annotations

from typing import ClassVar


class EngineError(Exception):
    code: ClassVar[str] = "server_error"
    status: ClassVar[int] = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message: str = message


class InvalidRequest(EngineError):
    code = "invalid_request"
    status = 400


class UnknownModel(EngineError):
    code = "model_not_found"
    status = 404


class NotLoaded(EngineError):
    code = "not_loaded"
    status = 409


class LoadFailed(EngineError):
    code = "load_failed"
    status = 500


class GenerationFailed(EngineError):
    code = "generation_failed"
    status = 500


class MissingParts(EngineError):
    code = "missing_parts"
    status = 503
