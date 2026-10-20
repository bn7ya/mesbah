from typing import Any

from rest_framework import serializers

from apps.models.serializers import FitSerializer
from apps.training.models import TrainingRun


class VersionRefSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    number = serializers.IntegerField(read_only=True)


class HyperparamsSerializer(serializers.Serializer[dict[str, Any]]):
    epochs = serializers.FloatField(min_value=0.1, max_value=100, required=False)
    max_steps = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    learning_rate = serializers.FloatField(min_value=1e-7, max_value=1e-2, required=False)
    lora_rank = serializers.ChoiceField(choices=[4, 8, 16, 32, 64, 128, 256], required=False)
    lora_alpha = serializers.IntegerField(min_value=1, max_value=1024, required=False)
    lora_dropout = serializers.FloatField(min_value=0, max_value=0.5, required=False)
    use_rslora = serializers.BooleanField(required=False)
    train_biases = serializers.BooleanField(required=False)
    max_seq_len = serializers.IntegerField(min_value=128, max_value=131072, required=False)
    batch_size = serializers.IntegerField(min_value=1, max_value=64, required=False)
    grad_accum = serializers.IntegerField(min_value=1, max_value=256, required=False)
    quantize_4bit = serializers.BooleanField(required=False)
    gradient_checkpointing = serializers.BooleanField(required=False)


class RunDatasetSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    name = serializers.CharField(read_only=True)
    rows = serializers.IntegerField(read_only=True)
    max_rows = serializers.IntegerField(min_value=1, required=False, allow_null=True, default=None)


class RunSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField(read_only=True)
    project = serializers.UUIDField(read_only=True)
    kind = serializers.ChoiceField(choices=TrainingRun.Kind.choices, read_only=True)
    draft = serializers.UUIDField(read_only=True, allow_null=True)
    corrections_from = serializers.ListField(child=serializers.UUIDField(), read_only=True)
    name = serializers.CharField(read_only=True, allow_blank=True)
    notes = serializers.CharField(read_only=True, allow_blank=True)
    starts_from = VersionRefSerializer(read_only=True, allow_null=True)
    version = VersionRefSerializer(read_only=True, allow_null=True)
    use_corrections = serializers.BooleanField(read_only=True)
    datasets = RunDatasetSerializer(many=True, read_only=True)
    hyperparams = serializers.DictField(read_only=True)
    activate_when_done = serializers.BooleanField(read_only=True)
    status = serializers.ChoiceField(choices=TrainingRun.Status.choices, read_only=True)
    stage = serializers.CharField(read_only=True, allow_blank=True)
    examples = serializers.IntegerField(read_only=True, allow_null=True)
    skipped = serializers.IntegerField(read_only=True, allow_null=True)
    tokens = serializers.IntegerField(read_only=True, allow_null=True)
    step = serializers.IntegerField(read_only=True)
    total_steps = serializers.IntegerField(read_only=True)
    epoch = serializers.FloatField(read_only=True, allow_null=True)
    loss = serializers.FloatField(read_only=True, allow_null=True)
    max_seq_len = serializers.IntegerField(read_only=True, allow_null=True)
    gpu_indices = serializers.ListField(child=serializers.IntegerField(), read_only=True)
    error_code = serializers.CharField(read_only=True, allow_blank=True)
    error_detail = serializers.CharField(read_only=True, allow_blank=True)
    cancel_requested = serializers.BooleanField(read_only=True)
    started_at = serializers.DateTimeField(read_only=True, allow_null=True)
    finished_at = serializers.DateTimeField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)
    created_by = serializers.CharField(read_only=True, allow_null=True)


class NewRunSerializer(serializers.Serializer[dict[str, Any]]):
    project = serializers.UUIDField()
    starts_from = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField(required=False, allow_blank=True, max_length=120)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    use_corrections = serializers.BooleanField(required=False, default=True)
    datasets = RunDatasetSerializer(many=True, required=False)
    activate_when_done = serializers.BooleanField(required=False, default=True)
    hyperparams = HyperparamsSerializer(required=False)


class ProjectQuerySerializer(serializers.Serializer[dict[str, Any]]):
    project = serializers.UUIDField()


class MetricQuerySerializer(serializers.Serializer[dict[str, Any]]):
    after_step = serializers.IntegerField(min_value=0, required=False, default=0)


class MetricSerializer(serializers.Serializer[dict[str, Any]]):
    step = serializers.IntegerField(read_only=True)
    epoch = serializers.FloatField(read_only=True, allow_null=True)
    loss = serializers.FloatField(read_only=True, allow_null=True)
    learning_rate = serializers.FloatField(read_only=True, allow_null=True)
    grad_norm = serializers.FloatField(read_only=True, allow_null=True)


class PlanSerializer(serializers.Serializer[dict[str, Any]]):
    hyperparams = HyperparamsSerializer(read_only=True)
    corrections = serializers.IntegerField(read_only=True)
    fit = FitSerializer(read_only=True)
    gpu_indices = serializers.ListField(child=serializers.IntegerField(), read_only=True)


class TurnSerializer(serializers.Serializer[dict[str, Any]]):
    role = serializers.CharField(read_only=True)
    content = serializers.CharField(read_only=True, allow_blank=True)
    thinking = serializers.CharField(read_only=True, required=False)


class ConversationRefSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField(read_only=True)
    title = serializers.CharField(read_only=True, allow_blank=True)


class ExampleSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField(read_only=True)
    conversation = ConversationRefSerializer(read_only=True)
    messages = TurnSerializer(many=True, read_only=True)
    corrected = serializers.BooleanField(read_only=True)
    thinking_corrected = serializers.BooleanField(read_only=True)
    approved_by = serializers.CharField(read_only=True, allow_null=True)
    updated_at = serializers.DateTimeField(read_only=True)
