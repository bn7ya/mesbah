from typing import Any

from rest_framework import serializers

from apps.chat.models import Message


class NamedRefSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)


class ReplySettingsSerializer(serializers.Serializer[dict[str, Any]]):
    temperature = serializers.FloatField(min_value=0, max_value=2, required=False)
    top_p = serializers.FloatField(min_value=0, max_value=1, required=False)
    max_tokens = serializers.IntegerField(min_value=1, max_value=32768, required=False)


class ConversationSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField(read_only=True)
    project = serializers.UUIDField(read_only=True)
    title = serializers.CharField(read_only=True, allow_blank=True)
    version = NamedRefSerializer(read_only=True, allow_null=True)
    engine = NamedRefSerializer(read_only=True, allow_null=True)
    system_prompt = serializers.CharField(read_only=True, allow_blank=True)
    thinking = serializers.BooleanField(read_only=True)
    generation = ReplySettingsSerializer(read_only=True)
    message_count = serializers.IntegerField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class ConversationListQuerySerializer(serializers.Serializer[dict[str, Any]]):
    project = serializers.UUIDField()


class NewConversationSerializer(serializers.Serializer[dict[str, Any]]):
    project = serializers.UUIDField()
    title = serializers.CharField(required=False, allow_blank=True, max_length=200)
    version = serializers.UUIDField(required=False, allow_null=True)
    thinking = serializers.BooleanField(required=False)


class ConversationChangeSerializer(serializers.Serializer[dict[str, Any]]):
    title = serializers.CharField(required=False, allow_blank=True, max_length=200)
    version = serializers.UUIDField(required=False, allow_null=True)
    engine = serializers.UUIDField(required=False, allow_null=True)
    system_prompt = serializers.CharField(required=False, allow_blank=True, max_length=20000)
    thinking = serializers.BooleanField(required=False)
    generation = ReplySettingsSerializer(required=False)


class MessageSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField(read_only=True)
    position = serializers.IntegerField(read_only=True)
    role = serializers.ChoiceField(choices=Message.Role.choices, read_only=True)
    status = serializers.ChoiceField(choices=Message.Status.choices, read_only=True)
    content = serializers.CharField(read_only=True, allow_blank=True)
    thinking = serializers.CharField(read_only=True, allow_blank=True)
    version = NamedRefSerializer(read_only=True, allow_null=True)
    engine_name = serializers.CharField(read_only=True, allow_blank=True)
    finish_reason = serializers.CharField(read_only=True, allow_blank=True)
    error_code = serializers.CharField(read_only=True, allow_blank=True)
    tokens_prompt = serializers.IntegerField(read_only=True, allow_null=True)
    tokens_completion = serializers.IntegerField(read_only=True, allow_null=True)
    latency_ms = serializers.IntegerField(read_only=True, allow_null=True)
    original_content = serializers.CharField(read_only=True, allow_null=True)
    original_thinking = serializers.CharField(read_only=True, allow_null=True)
    content_edited_at = serializers.DateTimeField(read_only=True, allow_null=True)
    thinking_edited_at = serializers.DateTimeField(read_only=True, allow_null=True)
    edited_by = serializers.CharField(read_only=True, allow_null=True)
    approved = serializers.BooleanField(read_only=True)
    approved_by = serializers.CharField(read_only=True, allow_null=True)
    include_in_training = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class AskSerializer(serializers.Serializer[dict[str, Any]]):
    content = serializers.CharField(max_length=100_000, trim_whitespace=False)

    def validate_content(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Write a message first.", code="blank")
        return value


class MessageEditSerializer(serializers.Serializer[dict[str, Any]]):
    seen = serializers.DateTimeField(help_text="The message's `updated_at` when it was opened.")
    content = serializers.CharField(required=False, max_length=100_000, trim_whitespace=False)
    thinking = serializers.CharField(
        required=False, allow_blank=True, max_length=100_000, trim_whitespace=False
    )
    include_in_training = serializers.BooleanField(required=False)

    def validate_content(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("A reply needs some text.", code="blank")
        return value


class RestoreSerializer(serializers.Serializer[dict[str, Any]]):
    seen = serializers.DateTimeField(help_text="The message's `updated_at` when it was opened.")
    part = serializers.ChoiceField(choices=["content", "thinking"])


class ApproveSerializer(serializers.Serializer[dict[str, Any]]):
    approved = serializers.BooleanField()
