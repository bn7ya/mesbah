from __future__ import annotations

from django.db import models

from apps.common.models import BaseModel


class Setting(BaseModel):
    key = models.CharField(max_length=100)
    value = models.JSONField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["key"],
                condition=models.Q(deleted_at__isnull=True),
                name="system_setting_key_alive",
            )
        ]

    def __str__(self) -> str:
        return self.key


class Secret(BaseModel):
    name = models.CharField(max_length=100)
    ciphertext = models.TextField()
    hint = models.CharField(max_length=8, blank=True)
    account = models.CharField(max_length=200, blank=True)

    class Meta(BaseModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(deleted_at__isnull=True),
                name="system_secret_name_alive",
            )
        ]

    def __str__(self) -> str:
        return self.name
