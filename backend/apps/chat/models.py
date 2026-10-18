from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


class Conversation(BaseModel):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="conversations"
    )
    version = models.ForeignKey(
        "versions.ModelVersion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="conversations",
    )
    engine = models.ForeignKey(
        "serving.Engine",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="conversations",
    )
    title = models.CharField(max_length=200, blank=True)
    system_prompt = models.TextField(blank=True)
    thinking = models.BooleanField(default=True)
    generation = models.JSONField(default=dict, blank=True)

    class Meta(BaseModel.Meta):
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.title or str(self.pk)


class Message(BaseModel):
    class Role(models.TextChoices):
        SYSTEM = "system"
        USER = "user"
        ASSISTANT = "assistant"

    class Status(models.TextChoices):
        STREAMING = "streaming"
        COMPLETE = "complete"
        STOPPED = "stopped"
        FAILED = "failed"

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    position = models.PositiveIntegerField()
    role = models.CharField(max_length=20, choices=Role.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COMPLETE)
    content = models.TextField(blank=True)
    thinking = models.TextField(blank=True)
    original_content = models.TextField(blank=True)
    original_thinking = models.TextField(blank=True)
    content_edited_at = models.DateTimeField(null=True, blank=True)
    thinking_edited_at = models.DateTimeField(null=True, blank=True)
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    version = models.ForeignKey(
        "versions.ModelVersion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    engine_name = models.CharField(max_length=120, blank=True)
    finish_reason = models.CharField(max_length=20, blank=True)
    error_code = models.CharField(max_length=40, blank=True)
    tokens_prompt = models.PositiveIntegerField(null=True, blank=True)
    tokens_completion = models.PositiveIntegerField(null=True, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    include_in_training = models.BooleanField(default=True)

    class Meta(BaseModel.Meta):
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "position"],
                condition=models.Q(deleted_at__isnull=True),
                name="chat_message_position_alive",
            )
        ]

    def __str__(self) -> str:
        return f"{self.role} #{self.position}"
