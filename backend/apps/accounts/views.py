"""Thin views. Parse, delegate to one service call, serialize the result."""
from __future__ import annotations

from django.middleware.csrf import get_token
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.serializers import IdentitySerializer, SignInSerializer
from apps.accounts.services import AccountService


class CsrfView(APIView):
    """Issues the CSRF cookie the SPA needs before its first unsafe request.

    Public by necessity: a client that is not signed in yet still has to be
    able to POST to `/api/auth/login/`.
    """

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
    """`POST /api/auth/login/` — start a session."""

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Sign in",
        description=(
            "Starts a session. Refused credentials answer 403, not 401: DRF "
            "downgrades AuthenticationFailed when no authenticator can offer a "
            "WWW-Authenticate challenge, and cookie auth has none. The reason "
            "is in the body."
        ),
        request=SignInSerializer,
        responses={200: IdentitySerializer, 403: None},
        auth=[],
    )
    def post(self, request: Request) -> Response:
        payload = SignInSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        service = AccountService()
        user = service.sign_in(request, **payload.validated_data)

        identity = AccountService(user).identity()
        return Response(IdentitySerializer(identity).data)


class SignOutView(APIView):
    """`POST /api/auth/logout/` — end the session."""

    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Sign out", request=None, responses={204: None})
    def post(self, request: Request) -> Response:
        AccountService(request.user).sign_out(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """`GET /api/auth/me/` — who the caller is, and which groups they are in.

    The frontend reads `groups` from here for its route guards and
    affordances — a convenience only. The security boundary is
    `permission_classes` on each endpoint.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Current user", responses={200: IdentitySerializer})
    def get(self, request: Request) -> Response:
        identity = AccountService(request.user).identity()
        return Response(IdentitySerializer(identity).data)
