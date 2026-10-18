from __future__ import annotations

from django.db import models

from apps.common.models import BaseModel


class ArchitectureDraft(BaseModel):
    name = models.CharField(max_length=120)
    notes = models.TextField(blank=True)
    design = models.JSONField(default=dict)
    tokenizer = models.CharField(max_length=200, blank=True)
    seq_len = models.PositiveIntegerField(default=1024)
    batch = models.PositiveIntegerField(default=8)

    class Meta(BaseModel.Meta):
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.name
