from __future__ import annotations

from django.db import models

from apps.common.models import BaseModel


class HubModel(BaseModel):
    class Status(models.TextChoices):
        QUEUED = "queued"
        DOWNLOADING = "downloading"
        READY = "ready"
        FAILED = "failed"
        CANCELLED = "cancelled"

    class Origin(models.TextChoices):
        HUB = "hub"
        TRAINED = "trained"

    class Family(models.TextChoices):
        DENSE_DECODER = "dense_decoder"
        MOE_DECODER = "moe_decoder"
        ENCODER_DECODER = "encoder_decoder"
        OTHER = "other"

    repo_id = models.CharField(max_length=200)
    origin = models.CharField(max_length=10, choices=Origin.choices, default=Origin.HUB)
    revision = models.CharField(max_length=64, blank=True)
    pipeline_tag = models.CharField(max_length=64, blank=True)
    family = models.CharField(max_length=20, choices=Family.choices, default=Family.OTHER)
    model_type = models.CharField(max_length=64, blank=True)
    architecture = models.JSONField(default=dict, blank=True)
    parameters = models.BigIntegerField(null=True, blank=True)
    active_parameters = models.BigIntegerField(null=True, blank=True)
    license = models.CharField(max_length=64, blank=True)
    gated = models.BooleanField(default=False)
    supports_thinking = models.BooleanField(default=False)
    has_chat_template = models.BooleanField(default=False)
    files = models.JSONField(default=list, blank=True)
    size_bytes = models.BigIntegerField(default=0)
    downloaded_bytes = models.BigIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    error_code = models.CharField(max_length=40, blank=True)
    local_path = models.TextField(blank=True)
    downloaded_at = models.DateTimeField(null=True, blank=True)
    cancel_requested = models.BooleanField(default=False)

    class Meta(BaseModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["repo_id"],
                condition=models.Q(deleted_at__isnull=True),
                name="models_hubmodel_repo_alive",
            )
        ]

    def __str__(self) -> str:
        return self.repo_id
