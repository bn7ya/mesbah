from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from apps.datasets.models import Dataset
from apps.datasets.repositories import DatasetRepository
from apps.models.models import HubModel
from apps.serving.services import DeploymentService
from apps.serving.services.errors import EngineFailed
from apps.training.models import TrainingMetric, TrainingRun
from apps.training.repositories import MetricRepository, RunRepository
from apps.training.repositories.run_repository import FINISHED
from apps.training.services.examples import ExampleService
from apps.versions.models import ModelVersion
from apps.versions.services import VersionService
from mesbah import parts
from mesbah.paths import ensure
from mesbah.train.contract import (
    BaseModelRef,
    ContractError,
    ExampleSource,
    Hyperparams,
    Status,
    TrainConfig,
)

logger: logging.Logger = logging.getLogger(__name__)

POLL_SECONDS: float = 2.0
LOG_TAIL: int = 2000
TRAINING_PARTS: tuple[str, ...] = ("torch", "transformers", "peft", "trl")
STAGES: dict[str, TrainingRun.Status] = {
    "begin": TrainingRun.Status.TRAINING,
    "log": TrainingRun.Status.TRAINING,
    "saving": TrainingRun.Status.SAVING,
}


class RunFailed(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(detail or code)
        self.code: str = code
        self.detail: str = detail


class RunnerService:
    def __init__(self, poll_seconds: float = POLL_SECONDS) -> None:
        self.poll_seconds: float = poll_seconds
        self.runs: RunRepository = RunRepository()
        self.metrics: MetricRepository = MetricRepository()
        self.datasets: DatasetRepository = DatasetRepository()
        self.examples: ExampleService = ExampleService()

    def run(self, run_id: str) -> None:
        run: TrainingRun | None = self.runs.with_project(run_id)
        if run is None or run.status in FINISHED:
            return
        if run.status != TrainingRun.Status.QUEUED:
            self._end(run, TrainingRun.Status.FAILED, "interrupted")
            return
        try:
            config: TrainConfig = self._prepare(run)
            self._release_gpu()
            self._supervise(run, config)
        except RunFailed as failure:
            self._end(run, TrainingRun.Status.FAILED, failure.code, failure.detail)

    def _prepare(self, run: TrainingRun) -> TrainConfig:
        folder: Path = ensure(Path(settings.MESBAH_DATA_DIR) / "runs" / str(run.pk))
        run = self.runs.update(
            run,
            status=TrainingRun.Status.PREPARING,
            stage="data",
            run_dir=str(folder),
            started_at=timezone.now(),
        )
        if not settings.MESBAH_FAKE_TRAINER and not all(
            parts.installed(name) for name in TRAINING_PARTS
        ):
            raise RunFailed("training_parts_missing")
        sources: list[ExampleSource] = self._sources(run, folder)
        if not sources:
            raise RunFailed("no_examples")
        try:
            config: TrainConfig = self._lora_config(run, folder, sources)
        except ContractError as error:
            raise RunFailed("bad_settings", str(error)) from error
        config.write(folder / "config.json")
        return config

    def _sources(self, run: TrainingRun, folder: Path) -> list[ExampleSource]:
        sources: list[ExampleSource] = []
        corrections: Path = folder / "corrections-0.jsonl"
        if run.use_corrections and self.examples.write(str(run.project_id), corrections):
            sources.append(ExampleSource(path=str(corrections)))
        for entry in run.datasets:
            dataset: Dataset | None = self.datasets.find(entry["id"])
            if dataset is not None and dataset.file_path and Path(dataset.file_path).is_file():
                sources.append(
                    ExampleSource(path=dataset.file_path, max_rows=entry.get("max_rows"))
                )
        return sources

    def _lora_config(
        self, run: TrainingRun, folder: Path, sources: list[ExampleSource]
    ) -> TrainConfig:
        base: HubModel | None = run.project.base_model
        if base is None or not base.local_path:
            raise RunFailed("base_model_not_ready")
        parent: ModelVersion | None = run.parent
        return TrainConfig(
            run_id=str(run.pk),
            base=BaseModelRef(
                repo_id=base.repo_id, path=base.local_path, revision=base.revision or None
            ),
            output_dir=str(folder / "adapter"),
            events_path=str(folder / "events.jsonl"),
            status_path=str(folder / "status.json"),
            cancel_path=str(folder / "cancel"),
            examples=tuple(sources),
            parent_adapter=parent.storage_dir
            if parent is not None and parent.kind == ModelVersion.Kind.LORA
            else None,
            hyperparams=Hyperparams.from_json(run.hyperparams),
            gpu_indices=tuple(run.gpu_indices),
        )

    def _release_gpu(self) -> None:
        try:
            DeploymentService(AnonymousUser()).release()
        except EngineFailed:
            logger.warning("The built-in engine did not unload before training.")

    def _supervise(self, run: TrainingRun, config: TrainConfig) -> None:
        folder: Path = Path(run.run_dir)
        command: list[str] = [sys.executable, "-m", "mesbah.train", "--config"]
        command.append(str(folder / "config.json"))
        if settings.MESBAH_FAKE_TRAINER:
            command.append("--fake")
        environment: dict[str, str] = {
            **os.environ,
            "HF_HOME": str(Path(settings.MESBAH_DATA_DIR) / "hf"),
        }
        with (folder / "trainer.log").open("wb") as log:
            process: subprocess.Popen[bytes] = subprocess.Popen(  # noqa: S603
                command,
                cwd=settings.BASE_DIR,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            while True:
                finished: bool = process.poll() is not None
                run = self._read_events(run, Path(config.events_path))
                if not finished and self.runs.cancel_requested(str(run.pk)):
                    Path(config.cancel_path).touch()
                if finished:
                    break
                time.sleep(self.poll_seconds)
        self._settle(run, config)

    def _read_events(self, run: TrainingRun, path: Path) -> TrainingRun:
        if not path.exists():
            return run
        complete: list[str] = path.read_text(encoding="utf-8").split("\n")[:-1]
        fresh: list[str] = complete[run.events_read :]
        if not fresh:
            return run
        changes: dict[str, Any] = {"events_read": len(complete)}
        points: list[TrainingMetric] = []
        for line in fresh:
            try:
                event: object = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                _apply(event, changes, points, run)
        self.metrics.record(points)
        return self.runs.update(run, **changes)

    def _settle(self, run: TrainingRun, config: TrainConfig) -> None:
        status_path: Path = Path(config.status_path)
        try:
            outcome: Status = Status.read(status_path)
        except (OSError, ContractError, ValueError):
            self._end(run, TrainingRun.Status.FAILED, "trainer_crashed", _tail(run))
            return
        if outcome.status == "cancelled":
            self._end(run, TrainingRun.Status.CANCELLED)
            return
        if outcome.status == "failed" or outcome.adapter_dir is None:
            failure: tuple[str, str] = (
                ("failed", "")
                if outcome.error is None
                else (outcome.error.code, outcome.error.detail)
            )
            self._end(run, TrainingRun.Status.FAILED, *failure)
            return
        self._finish(run, self._keep(run, config, outcome), outcome)

    def _finish(self, run: TrainingRun, version: ModelVersion, outcome: Status) -> None:
        self.runs.update(
            run,
            status=TrainingRun.Status.COMPLETED,
            version=version,
            loss=outcome.metrics.final_loss if outcome.metrics.final_loss is not None else run.loss,
            finished_at=timezone.now(),
        )

    def _keep(self, run: TrainingRun, config: TrainConfig, outcome: Status) -> ModelVersion:
        identifier: uuid.UUID = uuid.uuid4()
        target: Path = ensure(Path(settings.MESBAH_DATA_DIR) / "versions" / str(run.project_id))
        stored: Path = target / str(identifier)
        shutil.move(str(outcome.adapter_dir), stored)
        hyperparams: Hyperparams = config.hyperparams
        base: HubModel | None = run.project.base_model
        versions: VersionService = VersionService(run.created_by or AnonymousUser())
        version: ModelVersion = versions.record_trained(
            run.project,
            run.parent,
            id=identifier,
            name=run.name,
            notes=run.notes,
            storage_dir=str(stored),
            lora_rank=outcome.delta.rank if outcome.delta else hyperparams.lora_rank,
            lora_alpha=float(hyperparams.lora_alpha),
            use_rslora=hyperparams.use_rslora,
            target_modules=_targets(stored),
            trains_biases=hyperparams.train_biases,
            size_bytes=outcome.size_bytes,
            full_size_bytes=0 if base is None else base.size_bytes,
            delta_stats={} if outcome.delta is None else outcome.delta.to_json(),
            metrics=outcome.metrics.to_json(),
        )
        if run.activate_when_done:
            versions.activate(str(version.pk))
        return version

    def _end(
        self, run: TrainingRun, status: TrainingRun.Status, code: str = "", detail: str = ""
    ) -> None:
        self.runs.update(
            run,
            status=status,
            error_code=code[:40],
            error_detail=detail[-LOG_TAIL:],
            finished_at=timezone.now(),
        )


def _apply(
    event: dict[str, object],
    changes: dict[str, Any],
    points: list[TrainingMetric],
    run: TrainingRun,
) -> None:
    name: object = event.get("event")
    if not isinstance(name, str):
        return
    if name in STAGES:
        changes["status"] = STAGES[name]
    if name == "loading":
        changes["stage"] = str(event.get("stage", ""))
    elif name == "data":
        changes.update(
            examples=_count(event.get("examples")),
            skipped=_count(event.get("skipped")),
            tokens=_count(event.get("tokens")),
        )
    elif name == "begin":
        changes.update(stage="training", total_steps=_count(event.get("total_steps")) or 0)
    elif name == "log":
        step: int = _count(event.get("step")) or 0
        changes.update(
            step=step,
            total_steps=_count(event.get("total_steps")) or changes.get("total_steps", 0),
            epoch=_number(event.get("epoch")),
            loss=_number(event.get("loss")),
        )
        points.append(
            TrainingMetric(
                run=run,
                step=step,
                epoch=_number(event.get("epoch")),
                loss=_number(event.get("loss")),
                learning_rate=_number(event.get("learning_rate")),
                grad_norm=_number(event.get("grad_norm")),
            )
        )
    elif name == "oom_retry":
        changes.update(stage="oom_retry", max_seq_len=_count(event.get("max_seq_len")))
    elif name == "error":
        changes.update(
            error_code=str(event.get("code", "failed"))[:40],
            error_detail=str(event.get("detail", ""))[-LOG_TAIL:],
        )


def _count(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _targets(adapter: Path) -> list[str]:
    try:
        settings_file: object = json.loads((adapter / "adapter_config.json").read_text())
    except (OSError, ValueError):
        return []
    targets: object = (
        settings_file.get("target_modules") if isinstance(settings_file, dict) else None
    )
    if isinstance(targets, str):
        return [targets]
    return sorted(str(name) for name in targets) if isinstance(targets, list) else []


def _tail(run: TrainingRun) -> str:
    try:
        return (Path(run.run_dir) / "trainer.log").read_text(errors="replace")[-LOG_TAIL:]
    except OSError:
        return ""
