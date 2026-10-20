from typing import Any
from urllib.parse import SplitResult, urlsplit

from rest_framework import serializers

from apps.serving.models import Engine


class LoadedBaseSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField(read_only=True)
    repo_id = serializers.CharField(read_only=True)


class LoadedProjectSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)


class LoadedVersionSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    number = serializers.IntegerField(read_only=True)
    project = LoadedProjectSerializer(read_only=True)


class EngineStateSerializer(serializers.Serializer[dict[str, Any]]):
    running = serializers.BooleanField(read_only=True)
    loaded = serializers.BooleanField(read_only=True)
    busy = serializers.BooleanField(read_only=True)
    device = serializers.CharField(read_only=True, allow_null=True)
    quantized = serializers.BooleanField(read_only=True)
    base_model = LoadedBaseSerializer(read_only=True, allow_null=True)
    versions = LoadedVersionSerializer(many=True, read_only=True)


class EngineSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    kind = serializers.ChoiceField(choices=Engine.Kind.choices, read_only=True)
    base_url = serializers.CharField(read_only=True)
    model_name = serializers.CharField(read_only=True, allow_blank=True)
    has_api_key = serializers.BooleanField(read_only=True)
    enabled = serializers.BooleanField(read_only=True)
    is_default = serializers.BooleanField(read_only=True)
    last_seen_at = serializers.DateTimeField(read_only=True, allow_null=True)
    state = EngineStateSerializer(read_only=True)


def checked_address(value: str) -> None:
    parsed: SplitResult = urlsplit(value.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise serializers.ValidationError(
            "Give the engine's address, starting with http:// or https://.", code="address"
        )


ENGINE_KINDS: list[str] = [kind for kind, _ in Engine.Kind.choices if kind != Engine.Kind.BUILTIN]


class NewEngineSerializer(serializers.Serializer[dict[str, Any]]):
    name = serializers.CharField(max_length=120)
    kind = serializers.ChoiceField(choices=ENGINE_KINDS)
    base_url = serializers.CharField(max_length=500, validators=[checked_address])
    model_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    api_key = serializers.CharField(required=False, allow_blank=True, write_only=True)
    is_default = serializers.BooleanField(required=False, default=False)


class EngineChangeSerializer(serializers.Serializer[dict[str, Any]]):
    name = serializers.CharField(max_length=120, required=False)
    base_url = serializers.CharField(max_length=500, required=False, validators=[checked_address])
    model_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    api_key = serializers.CharField(required=False, allow_blank=True, write_only=True)
    enabled = serializers.BooleanField(required=False)
    is_default = serializers.BooleanField(required=False)
