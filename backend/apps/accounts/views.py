from __future__ import annotations

from typing import Any

from django.contrib.auth.models import User
from django.middleware.csrf import get_token
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.serializers import (
    IdentitySerializer,
    SetupSerializer,
    SetupStatusSerializer,
    SignInSerializer,
)
from apps.accounts.services import AccountService, SetupService


class CsrfView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Issue a CSRF cookie",
        description="Sets the `csrftoken` cookie. Call once before signing in.",
        responses={204: None},
        auth=[],
    )
    def get(self, request: Request) -> Response:
        get_token(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SignInView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Sign in",
        description=(
            "Starts a session. Refused credentials answer 403, not 401: DRF "
            "downgrades AuthenticationFailed when no authenticator can offer a "
            "WWW-Authenticate challenge, and cookie auth has none. The reason is "
            "in the body."
        ),
        request=SignInSerializer,
        responses={200: IdentitySerializer, 403: None},
        auth=[],
    )
    def post(self, request: Request) -> Response:
        payload: SignInSerializer = SignInSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        service: AccountService = AccountService()
        user: User = service.sign_in(request, **payload.validated_data)

        identity: dict[str, Any] = AccountService(user).identity()
        return Response(IdentitySerializer(identity).data)


class SignOutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Sign out", request=None, responses={204: None})
    def post(self, request: Request) -> Response:
        AccountService(request.user).sign_out(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Current user", responses={200: IdentitySerializer})
    def get(self, request: Request) -> Response:
        identity: dict[str, Any] = AccountService(request.user).identity()
        return Response(IdentitySerializer(identity).data)


class SetupView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Whether Mesbah still needs its owner",
        description=(
            "True until the first account exists. While it is true, a one-time setup code is "
            "kept in the data folder and printed in the server log."
        ),
        responses={200: SetupStatusSerializer},
        auth=[],
    )
    def get(self, request: Request) -> Response:
        return Response(SetupStatusSerializer({"needed": SetupService().needed()}).data)

    @extend_schema(
        summary="Create the owner account",
        description="Needs the setup code. Signs the owner in. Refused once any account exists.",
        request=SetupSerializer,
        responses={201: IdentitySerializer, 403: None, 409: None},
        auth=[],
    )
    def post(self, request: Request) -> Response:
        payload: SetupSerializer = SetupSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        owner: User = SetupService().complete(request, **payload.validated_data)
        identity: dict[str, Any] = AccountService(owner).identity()
        return Response(IdentitySerializer(identity).data, status=status.HTTP_201_CREATED)
