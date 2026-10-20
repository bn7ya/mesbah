from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from django.contrib.auth.models import User
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.pages import PAGE_PARAMETERS, page_of, paginate
from apps.members.permissions import IsAdministrator
from apps.members.serializers import MemberChangeSerializer, MemberSerializer, NewMemberSerializer
from apps.members.services import MemberService


class MemberListView(APIView):
    permission_classes = [IsAdministrator]

    @extend_schema(
        summary="Members",
        parameters=PAGE_PARAMETERS,
        responses={200: page_of(MemberSerializer)},
    )
    def get(self, request: Request) -> Response:
        service: MemberService = MemberService(request.user)

        def render(members: Iterable[User]) -> list[Any]:
            return [MemberSerializer(service.describe(member)).data for member in members]

        return paginate(request, self, service.listing(), render)

    @extend_schema(
        summary="Add a member",
        request=NewMemberSerializer,
        responses={201: MemberSerializer},
    )
    def post(self, request: Request) -> Response:
        payload: NewMemberSerializer = NewMemberSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        member: dict[str, Any] = MemberService(request.user).add(**payload.validated_data)
        return Response(MemberSerializer(member).data, status=status.HTTP_201_CREATED)


class MemberDetailView(APIView):
    permission_classes = [IsAdministrator]

    @extend_schema(
        summary="Change a member's role or deactivate them",
        request=MemberChangeSerializer,
        responses={200: MemberSerializer},
    )
    def patch(self, request: Request, member_id: int) -> Response:
        payload: MemberChangeSerializer = MemberChangeSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        member: dict[str, Any] = MemberService(request.user).change(
            member_id, **payload.validated_data
        )
        return Response(MemberSerializer(member).data)
