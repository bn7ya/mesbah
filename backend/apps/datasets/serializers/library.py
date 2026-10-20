from typing import Any

from rest_framework import serializers

from apps.datasets.models import Dataset
from apps.datasets.serializers.hub import REPO_PATTERN
from apps.datasets.serializers.rows import MappingSerializer

DEFAULT_ROW_LIMIT: int = 10_000
MAX_ROW_LIMIT: int = 1_000_000


class DatasetSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True, allow_blank=True)
    # DRF pops declared fields, so a field may share its name with Field.source.
    source = serializers.ChoiceField(choices=Dataset.Source.choices, read_only=True)  # type: ignore[assignment]
    repo_id = serializers.CharField(read_only=True, allow_blank=True)
    config_name = serializers.CharField(read_only=True, allow_blank=True)
    split = serializers.CharField(read_only=True, allow_blank=True)
    file_name = serializers.CharField(read_only=True, allow_blank=True)
    format = serializers.ChoiceField(
        choices=Dataset.Format.choices, read_only=True, allow_blank=True
    )
    mapping = MappingSerializer(read_only=True, allow_null=True)
    row_limit = serializers.IntegerField(read_only=True, allow_null=True)
    source_rows = serializers.IntegerField(read_only=True, allow_null=True)
    status = serializers.ChoiceField(choices=Dataset.Status.choices, read_only=True)
    error_code = serializers.CharField(read_only=True, allow_blank=True)
    rows = serializers.IntegerField(read_only=True)
    skipped = serializers.IntegerField(read_only=True)
    size_bytes = serializers.IntegerField(read_only=True)
    sha256 = serializers.CharField(read_only=True, allow_blank=True)
    has_thinking = serializers.BooleanField(read_only=True)
    excerpt = serializers.CharField(read_only=True, allow_blank=True)
    created_by = serializers.CharField(read_only=True, allow_blank=True)
    created_at = serializers.DateTimeField(read_only=True)


class ImportSerializer(serializers.Serializer[dict[str, Any]]):
    repo_id = serializers.RegexField(REPO_PATTERN, max_length=200)
    config = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
    split = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
    row_limit = serializers.IntegerField(
        required=False, min_value=1, max_value=MAX_ROW_LIMIT, default=DEFAULT_ROW_LIMIT
    )
    mapping = MappingSerializer(required=False)


class UploadSerializer(serializers.Serializer[dict[str, Any]]):
    file = serializers.FileField(allow_empty_file=True)
    name = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")


class DatasetChangesSerializer(serializers.Serializer[dict[str, Any]]):
    name = serializers.CharField(required=False, max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, max_length=2000)
