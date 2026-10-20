from django.urls import URLPattern, URLResolver, path

from apps.chat.views import (
    ApproveMessageView,
    ConversationDetailView,
    ConversationListView,
    MessageListView,
    MessageView,
    ReplyView,
    RestoreMessageView,
)

app_name: str = "chat"

urlpatterns: list[URLPattern | URLResolver] = [
    path("", ConversationListView.as_view(), name="conversations"),
    path("<uuid:conversation_id>/", ConversationDetailView.as_view(), name="conversation"),
    path("<uuid:conversation_id>/messages/", MessageListView.as_view(), name="messages"),
    path("<uuid:conversation_id>/reply/", ReplyView.as_view(), name="reply"),
    path("messages/<uuid:message_id>/", MessageView.as_view(), name="message"),
    path("messages/<uuid:message_id>/restore/", RestoreMessageView.as_view(), name="restore"),
    path("messages/<uuid:message_id>/approve/", ApproveMessageView.as_view(), name="approve"),
]
