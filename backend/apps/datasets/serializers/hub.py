from typing import Any

from rest_framework import serializers

from apps.datasets.models import Dataset
from apps.datasets.serializers.rows import MappingSerializer, RowSerializer

REPO_PATTERN: str = r"^(?:[\w.-]+/)?[\w.-]+$"


class HubQuerySerializer(serializers.Serializer[dict[str, Any]]):
    search = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")


class HubDatasetSerializer(serializers.Serializer[dict[str, Any]]):
    repo_id = serializers.CharField(read_only=True)
    downloads = serializers.IntegerField(read_only=True)
    likes = serializers.IntegerField(read_only=True)
    license = serializers.CharField(read_only=True, allow_blank=True)
    gated = serializers.BooleanField(read_only=True)
    size_category = serializers.CharField(read_only=True, allow_blank=True)
    languages = serializers.ListField(child=serializers.CharField(), read_only=True)
    description = serializers.CharField(read_only=True, allow_blank=True)
    in_library = serializers.BooleanField(read_only=True)


class SplitSerializer(serializers.Serializer[dict[str, Any]]):
    name = serializers.CharField(read_only=True)
    rows = serializers.IntegerField(read_only=True, allow_null=True)


class ConfigSerializer(serializers.Serializer[dict[str, Any]]):
    name = serializers.CharField(read_only=True)
    splits = SplitSerializer(many=True, read_only=True)


class DatasetInspectionSerializer(HubDatasetSerializer):
    configs = ConfigSerializer(many=True, read_only=True)
    config = serializers.CharField(read_only=True)
    split = serializers.CharField(read_only=True)
    columns = serializers.ListField(child=serializers.CharField(), read_only=True)
    detected = serializers.ChoiceField(choices=Dataset.Format.choices, read_only=True)
    mapping = MappingSerializer(read_only=True)
    conversations = RowSerializer(many=True, read_only=True)
    sample_rows = serializers.IntegerField(read_only=True)
    sample_skipped = serializers.IntegerField(read_only=True)


class InspectQuerySerializer(serializers.Serializer[dict[str, Any]]):
    repo = serializers.RegexField(REPO_PATTERN, max_length=200)
    config = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
    split = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
    prompt = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
    reply = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
    thinking = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if bool(attrs["prompt"]) != bool(attrs["reply"]):
            raise serializers.ValidationError(
                {"reply": "Choose both the prompt and the reply column."}
            )
        return attrs
