from typing import Any

from rest_framework import serializers

from apps.versions.models import ModelVersion


class DeltaSummarySerializer(serializers.Serializer[dict[str, Any]]):
    total_norm = serializers.FloatField(read_only=True, allow_null=True)
    change_from_parent = serializers.FloatField(read_only=True, allow_null=True)
    parameters = serializers.IntegerField(read_only=True, allow_null=True)


class VersionSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField(read_only=True)
    number = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    notes = serializers.CharField(read_only=True, allow_blank=True)
    kind = serializers.ChoiceField(choices=ModelVersion.Kind.choices, read_only=True)
    parent_id = serializers.UUIDField(read_only=True, allow_null=True)
    is_active = serializers.BooleanField(read_only=True)
    children_count = serializers.IntegerField(read_only=True, allow_null=True)
    size_bytes = serializers.IntegerField(read_only=True)
    full_size_bytes = serializers.IntegerField(read_only=True)
    lora_rank = serializers.IntegerField(read_only=True, allow_null=True)
    trains_biases = serializers.BooleanField(read_only=True)
    delta = DeltaSummarySerializer(read_only=True, allow_null=True)
    metrics = serializers.DictField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    created_by = serializers.CharField(read_only=True, allow_null=True)


class VersionChangeSerializer(serializers.Serializer[dict[str, Any]]):
    name = serializers.CharField(required=False, max_length=120, trim_whitespace=True)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=4000)


class VersionListQuerySerializer(serializers.Serializer[dict[str, Any]]):
    project = serializers.UUIDField()
