from typing import Any

from rest_framework import serializers

from apps.models.models import HubModel


class FitSerializer(serializers.Serializer[dict[str, Any]]):
    verdict = serializers.ChoiceField(
        choices=["fits", "tight", "too_large", "cpu_only", "unknown"], read_only=True
    )
    required_bytes = serializers.IntegerField(read_only=True, allow_null=True)
    available_bytes = serializers.IntegerField(read_only=True)


class FitSetSerializer(serializers.Serializer[dict[str, Any]]):
    chat = FitSerializer(read_only=True)
    chat_full = FitSerializer(read_only=True)
    training = FitSerializer(read_only=True)


class LibraryRefSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField(read_only=True)
    status = serializers.ChoiceField(choices=HubModel.Status.choices, read_only=True)


class HubResultSerializer(serializers.Serializer[dict[str, Any]]):
    repo_id = serializers.CharField(read_only=True)
    downloads = serializers.IntegerField(read_only=True)
    likes = serializers.IntegerField(read_only=True)
    pipeline_tag = serializers.CharField(read_only=True, allow_blank=True)
    parameters = serializers.IntegerField(read_only=True, allow_null=True)
    license = serializers.CharField(read_only=True, allow_blank=True)
    gated = serializers.BooleanField(read_only=True)
    model_type = serializers.CharField(read_only=True, allow_blank=True)
    supports_thinking = serializers.BooleanField(read_only=True)
    fit = FitSetSerializer(read_only=True)
    in_library = LibraryRefSerializer(read_only=True, allow_null=True)


class ArchitectureSerializer(serializers.Serializer[dict[str, Any]]):
    family = serializers.ChoiceField(choices=HubModel.Family.choices, read_only=True)
    model_type = serializers.CharField(read_only=True, allow_blank=True)
    layers = serializers.IntegerField(read_only=True, allow_null=True)
    hidden_size = serializers.IntegerField(read_only=True, allow_null=True)
    heads = serializers.IntegerField(read_only=True, allow_null=True)
    kv_heads = serializers.IntegerField(read_only=True, allow_null=True)
    vocab_size = serializers.IntegerField(read_only=True, allow_null=True)
    context_length = serializers.IntegerField(read_only=True, allow_null=True)
    experts = serializers.IntegerField(read_only=True, allow_null=True)
    experts_per_token = serializers.IntegerField(read_only=True, allow_null=True)
    expert_size = serializers.IntegerField(read_only=True, allow_null=True)


class InspectionSerializer(HubResultSerializer):
    revision = serializers.CharField(read_only=True, allow_blank=True)
    family = serializers.ChoiceField(choices=HubModel.Family.choices, read_only=True)
    architecture = ArchitectureSerializer(read_only=True)
    active_parameters = serializers.IntegerField(read_only=True, allow_null=True)
    has_chat_template = serializers.BooleanField(read_only=True)
    downloadable = serializers.BooleanField(read_only=True)
    size_bytes = serializers.IntegerField(read_only=True)


class LibraryModelSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField(read_only=True)
    repo_id = serializers.CharField(read_only=True)
    revision = serializers.CharField(read_only=True, allow_blank=True)
    family = serializers.ChoiceField(choices=HubModel.Family.choices, read_only=True)
    model_type = serializers.CharField(read_only=True, allow_blank=True)
    architecture = ArchitectureSerializer(read_only=True)
    parameters = serializers.IntegerField(read_only=True, allow_null=True)
    active_parameters = serializers.IntegerField(read_only=True, allow_null=True)
    license = serializers.CharField(read_only=True, allow_blank=True)
    gated = serializers.BooleanField(read_only=True)
    supports_thinking = serializers.BooleanField(read_only=True)
    has_chat_template = serializers.BooleanField(read_only=True)
    size_bytes = serializers.IntegerField(read_only=True)
    downloaded_bytes = serializers.IntegerField(read_only=True)
    status = serializers.ChoiceField(choices=HubModel.Status.choices, read_only=True)
    error_code = serializers.CharField(read_only=True, allow_blank=True)
    downloaded_at = serializers.DateTimeField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)
    fit = FitSetSerializer(read_only=True)


class AddModelSerializer(serializers.Serializer[dict[str, Any]]):
    repo_id = serializers.RegexField(r"^[\w.-]+/[\w.-]+$", max_length=200)


class HubQuerySerializer(serializers.Serializer[dict[str, Any]]):
    search = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
    task = serializers.ChoiceField(
        choices=["text-generation", "text2text-generation", ""], required=False, default=""
    )


class InspectQuerySerializer(serializers.Serializer[dict[str, Any]]):
    repo = serializers.RegexField(r"^[\w.-]+/[\w.-]+$", max_length=200)
