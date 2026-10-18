from __future__ import annotations

from typing import Any

from django.contrib.auth.models import AnonymousUser, User
from django.db import transaction
from django.db.models import QuerySet
from rest_framework.exceptions import NotFound

from apps.datasets.models import Dataset
from apps.datasets.services import DatasetService
from apps.datasets.services.errors import NotReady
from apps.models.models import HubModel
from apps.projects.models import Project
from apps.projects.repositories import ProjectRepository
from apps.system.services import SystemService
from apps.training.models import TrainingMetric, TrainingRun
from apps.training.repositories import MetricRepository, RunRepository
from apps.training.repositories.run_repository import FINISHED
from apps.training.services.errors import (
    BaseNotDownloaded,
    NothingToLearn,
    RunStillGoing,
    WrongParent,
)
from apps.training.services.examples import ExampleService
from apps.versions.models import ModelVersion
from apps.versions.repositories import VersionRepository
from mesbah import sizing

GIB: int = 1024**3
LONG_CONTEXT_VRAM: int = 24 * GIB


class TrainingService:
    def __init__(self, user: User | AnonymousUser) -> None:
        self.user: User | AnonymousUser = user
        self.runs: RunRepository = RunRepository()
        self.metrics: MetricRepository = MetricRepository()
        self.projects: ProjectRepository = ProjectRepository()
        self.versions: VersionRepository = VersionRepository()
        self.examples: ExampleService = ExampleService()
        self.system: SystemService = SystemService(user)

    def project(self, project_id: str) -> Project:
        project: Project | None = self.projects.find(project_id)
        if project is None:
            raise NotFound
        return project

    def listing(self, project_id: str) -> QuerySet[TrainingRun]:
        return self.runs.of_project(str(self.project(project_id).pk))

    def find(self, run_id: str) -> TrainingRun:
        run: TrainingRun | None = self.runs.with_project(run_id)
        if run is None:
            raise NotFound
        return run

    def describe(self, run: TrainingRun) -> dict[str, Any]:
        return {
            "id": run.pk,
            "project": run.project_id,
            "name": run.name,
            "notes": run.notes,
            "starts_from": None if run.parent is None else _version(run.parent),
            "version": None if run.version is None else _version(run.version),
            "use_corrections": run.use_corrections,
            "datasets": run.datasets,
            "hyperparams": run.hyperparams,
            "activate_when_done": run.activate_when_done,
            "status": run.status,
            "stage": run.stage,
            "examples": run.examples,
            "skipped": run.skipped,
            "tokens": run.tokens,
            "step": run.step,
            "total_steps": run.total_steps,
            "epoch": run.epoch,
            "loss": run.loss,
            "max_seq_len": run.max_seq_len,
            "gpu_indices": run.gpu_indices,
            "error_code": run.error_code,
            "error_detail": run.error_detail,
            "cancel_requested": run.cancel_requested,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "created_at": run.created_at,
            "created_by": None if run.created_by is None else run.created_by.get_username(),
        }

    def plan(self, project_id: str) -> dict[str, Any]:
        project: Project = self.project(project_id)
        base: HubModel | None = project.base_model
        vram: int = self.system.usable_vram_bytes()
        parameters: int = 0 if base is None else base.parameters or 0
        return {
            "hyperparams": self.defaults(parameters, vram),
            "corrections": self.examples.corrections(str(project.pk)).count(),
            "fit": vars(sizing.fit(sizing.qlora_bytes(parameters) if parameters else None, vram)),
            "gpu_indices": self.system.selected_gpu_indices(),
        }

    @staticmethod
    def defaults(parameters: int, vram: int) -> dict[str, Any]:
        half: int = sizing.chat_bytes(parameters, four_bit=False) * 2
        return {
            "epochs": 2.0,
            "learning_rate": 2e-4,
            "lora_rank": 16,
            "lora_alpha": 32,
            "lora_dropout": 0.0,
            "use_rslora": False,
            "train_biases": False,
            "max_seq_len": 4096 if vram >= LONG_CONTEXT_VRAM else 2048,
            "batch_size": 1,
            "grad_accum": 8,
            "quantize_4bit": vram > 0 and sizing.fit(half, vram).verdict != "fits",
            "gradient_checkpointing": True,
        }

    @transaction.atomic
    def create(
        self,
        *,
        project: str,
        starts_from: str | None = None,
        hyperparams: dict[str, Any] | None = None,
        datasets: list[dict[str, Any]] | None = None,
        **fields: Any,
    ) -> TrainingRun:
        owner: Project = self.project(project)
        base: HubModel | None = owner.base_model
        if base is None or base.status != HubModel.Status.READY or not base.local_path:
            raise BaseNotDownloaded
        start: ModelVersion | None = self._parent(owner, starts_from)
        chosen: list[dict[str, Any]] = self.chosen_datasets(datasets or [])
        learns: bool = bool(chosen) or (
            bool(fields.get("use_corrections", True))
            and self.examples.corrections(str(owner.pk)).exists()
        )
        if not learns:
            raise NothingToLearn
        vram: int = self.system.usable_vram_bytes()
        run: TrainingRun = self.runs.create(
            created_by=self._actor(),
            project=owner,
            parent=start,
            datasets=chosen,
            hyperparams={**self.defaults(base.parameters or 0, vram), **(hyperparams or {})},
            gpu_indices=self.system.selected_gpu_indices(),
            **fields,
        )
        transaction.on_commit(lambda: _enqueue(str(run.pk)))
        return run

    def chosen_datasets(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        library: DatasetService = DatasetService(self.user)
        chosen: dict[str, dict[str, Any]] = {}
        for entry in entries:
            dataset: Dataset = library.find(entry["id"])
            if dataset.status != Dataset.Status.READY:
                raise NotReady
            chosen[str(dataset.pk)] = {
                "id": str(dataset.pk),
                "name": dataset.name,
                "rows": dataset.rows,
                "max_rows": entry.get("max_rows"),
            }
        return list(chosen.values())

    def cancel(self, run_id: str) -> TrainingRun:
        run: TrainingRun = self.find(run_id)
        if run.status in FINISHED:
            return run
        if run.status == TrainingRun.Status.QUEUED:
            return self.runs.update(run, cancel_requested=True, status=TrainingRun.Status.CANCELLED)
        return self.runs.update(run, cancel_requested=True)

    def remove(self, run_id: str) -> None:
        run: TrainingRun = self.find(run_id)
        if run.status not in FINISHED:
            raise RunStillGoing
        self.runs.soft_delete(run)

    def metrics_of(self, run_id: str, after_step: int) -> QuerySet[TrainingMetric]:
        return self.metrics.of_run(str(self.find(run_id).pk), after_step)

    def _parent(self, project: Project, parent: str | None) -> ModelVersion | None:
        if parent is None:
            return project.active_version
        version: ModelVersion | None = self.versions.find(parent, project=project)
        if version is None:
            raise WrongParent
        return version

    def _actor(self) -> User | None:
        return self.user if isinstance(self.user, User) else None


def _enqueue(run_id: str) -> None:
    from apps.training.tasks import train

    train.delay(run_id)


def _version(version: ModelVersion) -> dict[str, Any]:
    return {"id": version.pk, "name": str(version), "number": version.number}
