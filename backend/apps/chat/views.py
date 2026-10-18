from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from django.http import StreamingHttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat.models import Conversation, Message
from apps.chat.serializers import (
    ApproveSerializer,
    AskSerializer,
    ConversationChangeSerializer,
    ConversationListQuerySerializer,
    ConversationSerializer,
    MessageEditSerializer,
    MessageSerializer,
    NewConversationSerializer,
    RestoreSerializer,
)
from apps.chat.services import (
    ConversationService,
    MessageService,
    ReplyService,
    describe_message,
)
from apps.chat.services.reply_service import Turn
from apps.common.pages import PAGE_PARAMETERS, page_of, paginate
from apps.members.permissions import IsReviewer, ViewersReadReviewersWrite


class ConversationListView(APIView):
    permission_classes = [ViewersReadReviewersWrite]

    @extend_schema(
        operation_id="chat_conversations",
        summary="A project's conversations, newest first",
        parameters=[
            OpenApiParameter("project", str, required=True, description="The project's id."),
            *PAGE_PARAMETERS,
        ],
        responses={200: page_of(ConversationSerializer)},
    )
    def get(self, request: Request) -> Response:
        query: ConversationListQuerySerializer = ConversationListQuerySerializer(
            data=request.query_params
        )
        query.is_valid(raise_exception=True)
        service: ConversationService = ConversationService(request.user)

        def render(conversations: Iterable[Conversation]) -> list[Any]:
            return [ConversationSerializer(service.describe(row)).data for row in conversations]

        return paginate(
            request, self, service.listing(str(query.validated_data["project"])), render
        )

    @extend_schema(
        summary="Start a conversation",
        description="Without a version it follows the project's active version.",
        request=NewConversationSerializer,
        responses={201: ConversationSerializer},
    )
    def post(self, request: Request) -> Response:
        payload: NewConversationSerializer = NewConversationSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        fields: dict[str, Any] = dict(payload.validated_data)
        fields["project"] = str(fields["project"])
        created: dict[str, Any] = ConversationService(request.user).create(**fields)
        return Response(ConversationSerializer(created).data, status=status.HTTP_201_CREATED)


class ConversationDetailView(APIView):
    permission_classes = [ViewersReadReviewersWrite]

    @extend_schema(
        operation_id="chat_conversation",
        summary="One conversation",
        responses={200: ConversationSerializer},
    )
    def get(self, request: Request, conversation_id: str) -> Response:
        service: ConversationService = ConversationService(request.user)
        return Response(
            ConversationSerializer(service.describe(service.find(conversation_id))).data
        )

    @extend_schema(
        summary="Rename a conversation or change how it replies",
        request=ConversationChangeSerializer,
        responses={200: ConversationSerializer},
    )
    def patch(self, request: Request, conversation_id: str) -> Response:
        payload: ConversationChangeSerializer = ConversationChangeSerializer(
            data=request.data, partial=True
        )
        payload.is_valid(raise_exception=True)
        changed: dict[str, Any] = ConversationService(request.user).change(
            conversation_id, **payload.validated_data
        )
        return Response(ConversationSerializer(changed).data)

    @extend_schema(summary="Remove a conversation", request=None, responses={204: None})
    def delete(self, request: Request, conversation_id: str) -> Response:
        ConversationService(request.user).remove(conversation_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MessageListView(APIView):
    permission_classes = [ViewersReadReviewersWrite]

    @extend_schema(
        operation_id="chat_messages",
        summary="A conversation's messages, oldest first",
        parameters=PAGE_PARAMETERS,
        responses={200: page_of(MessageSerializer)},
    )
    def get(self, request: Request, conversation_id: str) -> Response:
        service: ConversationService = ConversationService(request.user)

        def render(messages: Iterable[Message]) -> list[Any]:
            return [MessageSerializer(describe_message(message)).data for message in messages]

        return paginate(request, self, service.messages_of(conversation_id), render)


class ReplyView(APIView):
    permission_classes = [IsReviewer]

    @extend_schema(
        operation_id="chat_reply",
        summary="Send a message and stream the reply",
        description=(
            "Server-sent events: `start` (both messages), `ready` (the engine answering), "
            "`thinking` and `content` (text as it arrives), then `done` (the saved reply) or "
            "`error` (a code, a message and the saved reply). Closing the stream stops the "
            "reply and keeps what arrived."
        ),
        request=AskSerializer,
        responses={(200, "text/event-stream"): OpenApiResponse(OpenApiTypes.STR)},
    )
    def post(self, request: Request, conversation_id: str) -> StreamingHttpResponse:
        payload: AskSerializer = AskSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        service: ReplyService = ReplyService(request.user)
        turn: Turn = service.begin(conversation_id, payload.validated_data["content"])

        def render(message: dict[str, Any]) -> dict[str, Any]:
            return dict(MessageSerializer(message).data)

        response: StreamingHttpResponse = StreamingHttpResponse(
            service.stream(turn, render), content_type="text/event-stream"
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


class MessageView(APIView):
    permission_classes = [ViewersReadReviewersWrite]

    @extend_schema(
        operation_id="chat_message", summary="One message", responses={200: MessageSerializer}
    )
    def get(self, request: Request, message_id: str) -> Response:
        return Response(
            MessageSerializer(describe_message(MessageService(request.user).find(message_id))).data
        )

    @extend_schema(
        summary="Correct a reply",
        description=(
            "Replaces the reply's text, its thinking chain, or both; the first correction keeps "
            "the original. A correction approves the reply for training. `seen` must be the "
            "`updated_at` the editor started from, or the answer is `409 message_changed`."
        ),
        request=MessageEditSerializer,
        responses={200: MessageSerializer},
    )
    def patch(self, request: Request, message_id: str) -> Response:
        payload: MessageEditSerializer = MessageEditSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        fields: dict[str, Any] = dict(payload.validated_data)
        edited: dict[str, Any] = MessageService(request.user).edit(
            message_id, seen=fields.pop("seen"), **fields
        )
        return Response(MessageSerializer(edited).data)


class RestoreMessageView(APIView):
    permission_classes = [IsReviewer]

    @extend_schema(
        summary="Put back what the model wrote",
        description="Undoes the corrections to the reply's text or its thinking chain.",
        request=RestoreSerializer,
        responses={200: MessageSerializer},
    )
    def post(self, request: Request, message_id: str) -> Response:
        payload: RestoreSerializer = RestoreSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        restored: dict[str, Any] = MessageService(request.user).restore(
            message_id, payload.validated_data["part"], seen=payload.validated_data["seen"]
        )
        return Response(MessageSerializer(restored).data)


class ApproveMessageView(APIView):
    permission_classes = [IsReviewer]

    @extend_schema(
        summary="Mark a reply right as it is, or take the mark back",
        description="Approved replies are what training learns from.",
        request=ApproveSerializer,
        responses={200: MessageSerializer},
    )
    def post(self, request: Request, message_id: str) -> Response:
        payload: ApproveSerializer = ApproveSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        approved: dict[str, Any] = MessageService(request.user).approve(
            message_id, payload.validated_data["approved"]
        )
        return Response(MessageSerializer(approved).data)
