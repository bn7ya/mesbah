from typing import Any

from rest_framework import serializers

from apps.models.models import HubModel
from apps.projects.models import Project


class GenerationSerializer(serializers.Serializer[dict[str, Any]]):
    temperature = serializers.FloatField(min_value=0, max_value=2)
    top_p = serializers.FloatField(min_value=0, max_value=1)
    max_tokens = serializers.IntegerField(min_value=1, max_value=32768)


class ProjectBaseModelSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField(read_only=True)
    repo_id = serializers.CharField(read_only=True)
    family = serializers.ChoiceField(choices=HubModel.Family.choices, read_only=True)
    parameters = serializers.IntegerField(read_only=True, allow_null=True)
    supports_thinking = serializers.BooleanField(read_only=True)
    status = serializers.ChoiceField(choices=HubModel.Status.choices, read_only=True)


class ActiveVersionSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField(read_only=True)
    number = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)


class ProjectSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    slug = serializers.SlugField(read_only=True)
    description = serializers.CharField(read_only=True, allow_blank=True)
    kind = serializers.ChoiceField(choices=Project.Kind.choices, read_only=True)
    base_model = ProjectBaseModelSerializer(read_only=True, allow_null=True)
    active_version = ActiveVersionSerializer(read_only=True, allow_null=True)
    system_prompt = serializers.CharField(read_only=True, allow_blank=True)
    thinking = serializers.BooleanField(read_only=True)
    generation = GenerationSerializer(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class NewProjectSerializer(serializers.Serializer[dict[str, Any]]):
    name = serializers.CharField(max_length=120, trim_whitespace=True)
    base_model = serializers.UUIDField()
    description = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    system_prompt = serializers.CharField(required=False, allow_blank=True, max_length=20000)
    thinking = serializers.BooleanField(required=False)


class ProjectChangeSerializer(serializers.Serializer[dict[str, Any]]):
    name = serializers.CharField(required=False, max_length=120, trim_whitespace=True)
    description = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    system_prompt = serializers.CharField(required=False, allow_blank=True, max_length=20000)
    thinking = serializers.BooleanField(required=False)
    generation = GenerationSerializer(required=False)
