from __future__ import annotations

from django.contrib.auth.models import AnonymousUser, User
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.openapi import AutoSchema
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from apps.serving.models import ApiKey
from apps.serving.services.api_key_service import ApiKeyService

SCHEME: str = "bearer"
KEY_INVALID: str = "This API key isn't valid. Create a new one on the Engines page."


class ApiKeyAuthentication(BaseAuthentication):
    def authenticate(self, request: Request) -> tuple[User, ApiKey] | None:
        scheme, _, secret = (
            get_authorization_header(request).decode(errors="replace").partition(" ")
        )
        if scheme.lower() != SCHEME or not secret.strip():
            return None
        key: ApiKey | None = ApiKeyService(AnonymousUser()).authenticate(secret.strip())
        if key is None or key.created_by is None:
            raise AuthenticationFailed(KEY_INVALID, code="invalid_api_key")
        return key.created_by, key

    def authenticate_header(self, request: Request) -> str:
        return 'Bearer realm="mesbah"'


class ApiKeyScheme(OpenApiAuthenticationExtension):  # type: ignore[no-untyped-call]
    target_class = "apps.serving.authentication.ApiKeyAuthentication"
    name = "apiKey"

    def get_security_definition(self, auto_schema: AutoSchema) -> dict[str, str]:
        return {"type": "http", "scheme": "bearer", "description": "A Mesbah API key."}
