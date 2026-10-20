from typing import Any

from rest_framework import serializers

from apps.training.serializers import RunDatasetSerializer


class DesignSerializer(serializers.Serializer[dict[str, Any]]):
    family = serializers.ChoiceField(choices=["dense_decoder", "moe_decoder", "encoder_decoder"])
    hidden_size = serializers.IntegerField()
    heads = serializers.IntegerField()
    intermediate_size = serializers.IntegerField()
    vocab_size = serializers.IntegerField()
    context_length = serializers.IntegerField()
    layers = serializers.IntegerField(required=False)
    kv_heads = serializers.IntegerField(required=False, allow_null=True)
    experts = serializers.IntegerField(required=False)
    experts_per_token = serializers.IntegerField(required=False)
    encoder_layers = serializers.IntegerField(required=False)
    decoder_layers = serializers.IntegerField(required=False)
    tie_embeddings = serializers.BooleanField(required=False)


class PartsSerializer(serializers.Serializer[dict[str, Any]]):
    embeddings = serializers.IntegerField(read_only=True)
    attention = serializers.IntegerField(read_only=True)
    feed_forward = serializers.IntegerField(read_only=True)
    router = serializers.IntegerField(read_only=True)
    norms = serializers.IntegerField(read_only=True)
    lm_head = serializers.IntegerField(read_only=True)


class CountsSerializer(serializers.Serializer[dict[str, Any]]):
    total = serializers.IntegerField(read_only=True)
    active = serializers.IntegerField(read_only=True)
    embeddings_share = serializers.FloatField(read_only=True)
    parts = PartsSerializer(read_only=True)


class DesignFitSerializer(serializers.Serializer[dict[str, Any]]):
    verdict = serializers.CharField(read_only=True)
    required_bytes = serializers.IntegerField(read_only=True, allow_null=True)
    available_bytes = serializers.IntegerField(read_only=True)


class MemorySerializer(serializers.Serializer[dict[str, Any]]):
    precision = serializers.CharField(read_only=True)
    weights_bytes = serializers.IntegerField(read_only=True)
    adamw_bytes = serializers.IntegerField(read_only=True)
    adamw_8bit_bytes = serializers.IntegerField(read_only=True)
    activation_bytes = serializers.IntegerField(read_only=True)
    training_bytes = serializers.IntegerField(read_only=True)
    training_8bit_bytes = serializers.IntegerField(read_only=True)
    fit = DesignFitSerializer(read_only=True)
    fit_8bit = DesignFitSerializer(read_only=True)


class EstimateSerializer(serializers.Serializer[dict[str, Any]]):
    design = DesignSerializer(read_only=True)
    counts = CountsSerializer(read_only=True)
    memory = MemorySerializer(read_only=True)
    note = serializers.CharField(read_only=True, allow_null=True)
    tokenizer_vocabulary = serializers.IntegerField(read_only=True, allow_null=True)


class EstimateRequestSerializer(serializers.Serializer[dict[str, Any]]):
    design = serializers.DictField()
    seq_len = serializers.IntegerField(min_value=64, max_value=131072, default=1024)
    batch = serializers.IntegerField(min_value=1, max_value=1024, default=8)
    tokenizer = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")


class PresetSerializer(serializers.Serializer[dict[str, Any]]):
    name = serializers.CharField(read_only=True)
    design = DesignSerializer(read_only=True)
    counts = CountsSerializer(read_only=True)


class PresetListSerializer(serializers.Serializer[dict[str, Any]]):
    presets = PresetSerializer(many=True, read_only=True)


class DraftSerializer(EstimateSerializer):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    notes = serializers.CharField(read_only=True, allow_blank=True)
    tokenizer = serializers.CharField(read_only=True, allow_blank=True)
    seq_len = serializers.IntegerField(read_only=True)
    batch = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    created_by = serializers.CharField(read_only=True, allow_null=True)


class NewDraftSerializer(serializers.Serializer[dict[str, Any]]):
    name = serializers.CharField(max_length=120)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    design = serializers.DictField()
    tokenizer = serializers.CharField(required=False, allow_blank=True, max_length=200)
    seq_len = serializers.IntegerField(min_value=64, max_value=131072, required=False)
    batch = serializers.IntegerField(min_value=1, max_value=1024, required=False)


class DraftChangeSerializer(NewDraftSerializer):
    name = serializers.CharField(max_length=120, required=False)
    design = serializers.DictField(required=False)


class TrainDesignSerializer(serializers.Serializer[dict[str, Any]]):
    name = serializers.CharField(max_length=120, help_text="The new project's name.")
    corrections_from = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
        help_text="Projects whose approved replies it learns.",
    )
    datasets = RunDatasetSerializer(
        many=True, required=False, help_text="Library datasets it learns."
    )
    hyperparams = serializers.DictField(required=False)


class TrainStartedSerializer(serializers.Serializer[dict[str, Any]]):
    project = serializers.UUIDField(read_only=True)
    run = serializers.UUIDField(read_only=True)
