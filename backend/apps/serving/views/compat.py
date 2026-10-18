from __future__ import annotations

from rest_framework import exceptions, status
from rest_framework.parsers import JSONParser
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.members.permissions import IsViewer
from apps.serving.authentication import ApiKeyAuthentication
from apps.serving.services.errors import EngineFailed
from apps.serving.services.gateway_service import UnknownModel

KEY_MISSING: str = "Send a Mesbah API key as a Bearer token."


def failure(exc: Exception) -> tuple[int, str, str]:
    if isinstance(exc, UnknownModel):
        return status.HTTP_404_NOT_FOUND, "model_not_found", f"There is no model {exc.name!r}."
    if isinstance(exc, exceptions.ValidationError):
        return status.HTTP_400_BAD_REQUEST, "invalid_request", _first(exc.detail)
    if isinstance(exc, exceptions.APIException):
        code: str = str(getattr(exc, "default_code", "error"))
        return exc.status_code, code, str(exc.detail)
    raise exc


def _first(detail: object) -> str:
    if isinstance(detail, dict) and detail:
        key: str = str(next(iter(detail)))
        return f"{key}: {_first(detail[key])}"
    if isinstance(detail, list) and detail:
        return _first(detail[0])
    return str(detail)


class CompatView(APIView):
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [IsViewer]
    parser_classes = [JSONParser]
    renderer_classes = [JSONRenderer]

    def body(self, code: str, message: str) -> dict[str, object]:
        return {"error": {"message": message, "type": "invalid_request_error", "code": code}}

    def unauthorized(self, message: str) -> Response:
        response: Response = Response(
            self.body("invalid_api_key", message), status=status.HTTP_401_UNAUTHORIZED
        )
        response["WWW-Authenticate"] = 'Bearer realm="mesbah"'
        return response

    def handle_exception(self, exc: Exception) -> Response:
        if isinstance(exc, exceptions.NotAuthenticated):
            return self.unauthorized(KEY_MISSING)
        if isinstance(exc, exceptions.AuthenticationFailed):
            return self.unauthorized(str(exc.detail))
        code: int
        name: str
        message: str
        code, name, message = failure(exc)
        if isinstance(exc, EngineFailed):
            name = str(exc.default_code)
        return Response(self.body(name, message), status=code)
