from typing import Any

from rest_framework import serializers


class ApiKeySerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    prefix = serializers.CharField(read_only=True)
    owner = serializers.CharField(read_only=True, allow_null=True)
    last_used_at = serializers.DateTimeField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)


class NewApiKeySerializer(serializers.Serializer[dict[str, Any]]):
    name = serializers.CharField(max_length=120, trim_whitespace=True)


class CreatedApiKeySerializer(ApiKeySerializer):
    key = serializers.CharField(read_only=True, help_text="Shown once; only its digest is kept.")
