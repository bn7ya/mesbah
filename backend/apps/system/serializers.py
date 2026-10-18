from typing import Any

from rest_framework import serializers

MAX_TOKEN_LENGTH: int = 200


class GpuSerializer(serializers.Serializer[dict[str, Any]]):
    index = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    memory_bytes = serializers.IntegerField(read_only=True)
    compute_capability = serializers.CharField(read_only=True, allow_null=True)


class MachineSerializer(serializers.Serializer[dict[str, Any]]):
    gpus = GpuSerializer(many=True, read_only=True)
    driver = serializers.CharField(read_only=True, allow_null=True)
    ram_bytes = serializers.IntegerField(read_only=True)
    cpu_count = serializers.IntegerField(read_only=True)
    system = serializers.CharField(read_only=True)
    python = serializers.CharField(read_only=True)


class StorageSerializer(serializers.Serializer[dict[str, Any]]):
    path = serializers.CharField(read_only=True)
    free_bytes = serializers.IntegerField(read_only=True)
    total_bytes = serializers.IntegerField(read_only=True)


class PartSerializer(serializers.Serializer[dict[str, Any]]):
    name = serializers.CharField(read_only=True)
    purpose = serializers.CharField(read_only=True)
    version = serializers.CharField(read_only=True, allow_null=True)
    cuda = serializers.BooleanField(read_only=True, allow_null=True)


class HuggingFaceSerializer(serializers.Serializer[dict[str, Any]]):
    configured = serializers.BooleanField(read_only=True)
    hint = serializers.CharField(read_only=True, allow_blank=True)
    account = serializers.CharField(read_only=True, allow_blank=True)


class SystemOverviewSerializer(serializers.Serializer[dict[str, Any]]):
    machine = MachineSerializer(read_only=True)
    selected_gpus = serializers.ListField(child=serializers.IntegerField(), read_only=True)
    gpu_choice = serializers.ChoiceField(choices=["automatic", "chosen"], read_only=True)
    usable_vram_bytes = serializers.IntegerField(read_only=True)
    storage = StorageSerializer(read_only=True)
    parts = PartSerializer(many=True, read_only=True)
    huggingface = HuggingFaceSerializer(read_only=True)


class GpuSelectionSerializer(serializers.Serializer[dict[str, Any]]):
    gpus = serializers.ListField(child=serializers.IntegerField(min_value=0), allow_empty=True)


class HuggingFaceTokenSerializer(serializers.Serializer[dict[str, Any]]):
    token = serializers.CharField(
        max_length=MAX_TOKEN_LENGTH, trim_whitespace=True, write_only=True
    )
