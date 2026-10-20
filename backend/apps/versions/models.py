from __future__ import annotations

from django.db import models

from apps.common.models import BaseModel


class ModelVersion(BaseModel):
    class Kind(models.TextChoices):
        BASE = "base"
        SCRATCH_ROOT = "scratch_root"
        LORA = "lora"

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="versions"
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children"
    )
    number = models.PositiveIntegerField()
    name = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    storage_dir = models.TextField(blank=True)
    lora_rank = models.PositiveIntegerField(null=True, blank=True)
    lora_alpha = models.FloatField(null=True, blank=True)
    use_rslora = models.BooleanField(default=False)
    target_modules = models.JSONField(default=list, blank=True)
    trains_biases = models.BooleanField(default=False)
    size_bytes = models.BigIntegerField(default=0)
    full_size_bytes = models.BigIntegerField(default=0)
    delta_stats = models.JSONField(default=dict, blank=True)
    metrics = models.JSONField(default=dict, blank=True)

    class Meta(BaseModel.Meta):
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "number"],
                condition=models.Q(deleted_at__isnull=True),
                name="versions_number_per_project_alive",
            )
        ]

    def __str__(self) -> str:
        return self.name or f"v{self.number}"


class Export(BaseModel):
    class Format(models.TextChoices):
        LORA = "lora"
        MERGED = "merged"
        GGUF = "gguf"

    class Status(models.TextChoices):
        QUEUED = "queued"
        RUNNING = "running"
        READY = "ready"
        FAILED = "failed"

    version = models.ForeignKey(ModelVersion, on_delete=models.CASCADE, related_name="exports")
    format = models.CharField(max_length=20, choices=Format.choices)
    out_type = models.CharField(max_length=10, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    error_code = models.CharField(max_length=40, blank=True)
    error_detail = models.TextField(blank=True)
    path = models.TextField(blank=True)
    size_bytes = models.BigIntegerField(default=0)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.version} as {self.format}"
