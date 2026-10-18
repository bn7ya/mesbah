from __future__ import annotations

from django.db import models

from apps.common.models import BaseModel


def default_generation() -> dict[str, float | int]:
    return {"temperature": 0.7, "top_p": 0.9, "max_tokens": 1024}


class Project(BaseModel):
    class Kind(models.TextChoices):
        FINETUNE = "finetune"
        SCRATCH = "scratch"

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=80)
    description = models.TextField(blank=True)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.FINETUNE)
    base_model = models.ForeignKey(
        "models.HubModel",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="projects",
    )
    active_version = models.ForeignKey(
        "versions.ModelVersion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    system_prompt = models.TextField(blank=True)
    thinking = models.BooleanField(default=True)
    generation = models.JSONField(default=default_generation)

    class Meta(BaseModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["slug"],
                condition=models.Q(deleted_at__isnull=True),
                name="projects_project_slug_alive",
            )
        ]

    def __str__(self) -> str:
        return self.name
