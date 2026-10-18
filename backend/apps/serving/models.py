from __future__ import annotations

from django.db import models

from apps.common.models import BaseModel


class Engine(BaseModel):
    class Kind(models.TextChoices):
        BUILTIN = "builtin"
        VLLM = "vllm"
        LLAMACPP = "llamacpp"
        OLLAMA = "ollama"
        OPENAI = "openai"

    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    base_url = models.CharField(max_length=500, blank=True)
    model_name = models.CharField(max_length=200, blank=True)
    sealed_api_key = models.TextField(blank=True)
    enabled = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_default"],
                condition=models.Q(deleted_at__isnull=True, is_default=True),
                name="serving_one_default_engine",
            )
        ]

    def __str__(self) -> str:
        return self.name


class Deployment(BaseModel):
    class Status(models.TextChoices):
        LOADING = "loading"
        READY = "ready"
        FAILED = "failed"
        UNLOADED = "unloaded"

    engine = models.ForeignKey(Engine, on_delete=models.CASCADE, related_name="deployments")
    version = models.ForeignKey(
        "versions.ModelVersion", on_delete=models.CASCADE, related_name="deployments"
    )
    served_name = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.LOADING)
    error_code = models.CharField(max_length=40, blank=True)
    loaded_at = models.DateTimeField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["engine", "version"],
                condition=models.Q(deleted_at__isnull=True),
                name="serving_deployment_alive",
            )
        ]

    def __str__(self) -> str:
        return f"{self.version} on {self.engine}"


class ApiKey(BaseModel):
    name = models.CharField(max_length=120)
    prefix = models.CharField(max_length=16)
    digest = models.CharField(max_length=64, unique=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.prefix}…)"
