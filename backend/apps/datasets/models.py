from __future__ import annotations

from django.db import models

from apps.common.models import BaseModel


class Dataset(BaseModel):
    class Source(models.TextChoices):
        HUB = "hub"
        UPLOAD = "upload"

    class Status(models.TextChoices):
        QUEUED = "queued"
        IMPORTING = "importing"
        READY = "ready"
        FAILED = "failed"
        CANCELLED = "cancelled"

    class Format(models.TextChoices):
        MESSAGES = "messages"
        SHAREGPT = "sharegpt"
        INSTRUCTION = "instruction"
        PROMPT_COMPLETION = "prompt_completion"
        TEXT = "text"
        UNSUPPORTED = "unsupported"

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    source = models.CharField(max_length=10, choices=Source.choices)
    repo_id = models.CharField(max_length=200, blank=True)
    config_name = models.CharField(max_length=200, blank=True)
    split = models.CharField(max_length=200, blank=True)
    revision = models.CharField(max_length=64, blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    mapping = models.JSONField(default=dict, blank=True)
    format = models.CharField(max_length=20, choices=Format.choices, blank=True)
    row_limit = models.PositiveIntegerField(null=True, blank=True)
    source_rows = models.BigIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    error_code = models.CharField(max_length=40, blank=True)
    rows = models.BigIntegerField(default=0)
    skipped = models.BigIntegerField(default=0)
    size_bytes = models.BigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    has_thinking = models.BooleanField(default=False)
    preview = models.JSONField(default=list, blank=True)
    file_path = models.TextField(blank=True)
    cancel_requested = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.name
