from __future__ import annotations

from django.db import models

from apps.common.models import BaseModel


class TrainingRun(BaseModel):
    class Status(models.TextChoices):
        QUEUED = "queued"
        PREPARING = "preparing"
        TRAINING = "training"
        SAVING = "saving"
        COMPLETED = "completed"
        FAILED = "failed"
        CANCELLED = "cancelled"

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="training_runs"
    )
    parent = models.ForeignKey(
        "versions.ModelVersion",
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
        related_name="training_runs",
    )
    name = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    use_corrections = models.BooleanField(default=True)
    datasets = models.JSONField(default=list, blank=True)
    hyperparams = models.JSONField(default=dict, blank=True)
    activate_when_done = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    stage = models.CharField(max_length=20, blank=True)
    examples = models.PositiveIntegerField(null=True, blank=True)
    skipped = models.PositiveIntegerField(null=True, blank=True)
    tokens = models.PositiveBigIntegerField(null=True, blank=True)
    step = models.PositiveIntegerField(default=0)
    total_steps = models.PositiveIntegerField(default=0)
    epoch = models.FloatField(null=True, blank=True)
    loss = models.FloatField(null=True, blank=True)
    max_seq_len = models.PositiveIntegerField(null=True, blank=True)
    gpu_indices = models.JSONField(default=list, blank=True)
    run_dir = models.TextField(blank=True)
    events_read = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=40, blank=True)
    error_detail = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    cancel_requested = models.BooleanField(default=False)

    class Meta(BaseModel.Meta):
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name or str(self.pk)


class TrainingMetric(BaseModel):
    run = models.ForeignKey(TrainingRun, on_delete=models.CASCADE, related_name="metrics")
    step = models.PositiveIntegerField()
    epoch = models.FloatField(null=True, blank=True)
    loss = models.FloatField(null=True, blank=True)
    learning_rate = models.FloatField(null=True, blank=True)
    grad_norm = models.FloatField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        ordering = ["step"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "step"],
                condition=models.Q(deleted_at__isnull=True),
                name="training_metric_step_alive",
            )
        ]

    def __str__(self) -> str:
        return f"{self.run_id} @ {self.step}"
