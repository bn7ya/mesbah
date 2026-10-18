from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from django.utils import timezone

from apps.architect.models import ArchitectureDraft
from apps.models.models import HubModel
from apps.models.repositories import HubModelRepository
from apps.projects.models import Project
from apps.projects.services import ProjectService
from apps.training.models import TrainingRun
from apps.versions.models import ModelVersion
from mesbah import architect, sizing
from mesbah.paths import ensure
from mesbah.train.contract import (
    BaseModelRef,
    ExampleSource,
    Hyperparams,
    Pretrain,
    Status,
    TrainConfig,
)

TRAINED_PREFIX: str = "local/"
TEMPLATE_FILES: tuple[str, ...] = ("chat_template.jinja", "tokenizer_config.json")


def trained_repo_id(project: Project) -> str:
    return f"{TRAINED_PREFIX}{project.slug}"


def pretrain_config(
    run: TrainingRun, folder: Path, sources: list[ExampleSource]
) -> TrainConfig | None:
    draft: ArchitectureDraft | None = run.draft
    if draft is None:
        return None
    try:
        design: architect.Design = architect.Design.from_json(draft.design)
    except architect.DesignError:
        return None
    settings_: dict[str, Any] = dict(run.hyperparams)
    pretrain: object = settings_.pop("pretrain", {})
    return TrainConfig(
        run_id=str(run.pk),
        base=BaseModelRef(repo_id=trained_repo_id(run.project)),
        output_dir=str(folder / "model"),
        events_path=str(folder / "events.jsonl"),
        status_path=str(folder / "status.json"),
        cancel_path=str(folder / "cancel"),
        examples=tuple(sources),
        hyperparams=Hyperparams.from_json(settings_),
        gpu_indices=tuple(run.gpu_indices),
        kind="pretrain",
        architecture="seq2seq" if design.family == "encoder_decoder" else "causal",
        model_config=architect.to_hf_config(design),
        tokenizer=draft.tokenizer,
        pretrain=Pretrain.from_json(pretrain if isinstance(pretrain, dict) else {}),
    )


def keep_model(run: TrainingRun, outcome: Status) -> ModelVersion:
    target: Path = ensure(Path(settings.MESBAH_DATA_DIR) / "models" / "trained")
    folder: Path = target / f"{run.project.slug}-{run.pk.hex[:8]}"
    shutil.move(str(outcome.model_dir), folder)
    config: object = json.loads((folder / "config.json").read_text(encoding="utf-8"))
    shape: sizing.Architecture = sizing.architecture(config if isinstance(config, dict) else {})
    template: str | None = _chat_template(folder)
    actor: User | None = run.created_by
    model: HubModel = HubModelRepository().create(
        created_by=actor,
        repo_id=trained_repo_id(run.project),
        origin=HubModel.Origin.TRAINED,
        status=HubModel.Status.READY,
        pipeline_tag="text2text-generation"
        if shape.family == "encoder_decoder"
        else "text-generation",
        family=shape.family,
        model_type=shape.model_type,
        architecture=vars(shape),
        parameters=outcome.parameters,
        active_parameters=sizing.active_parameters(outcome.parameters, shape),
        supports_thinking=template is not None and sizing.supports_thinking(template),
        has_chat_template=template is not None,
        size_bytes=outcome.size_bytes,
        downloaded_bytes=outcome.size_bytes,
        local_path=str(folder),
        downloaded_at=timezone.now(),
    )
    return ProjectService(actor or AnonymousUser()).adopt(run.project, model)


def _chat_template(folder: Path) -> str | None:
    jinja: Path = folder / TEMPLATE_FILES[0]
    if jinja.is_file():
        return jinja.read_text(encoding="utf-8")
    try:
        tokenizer: object = json.loads((folder / TEMPLATE_FILES[1]).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    template: object = tokenizer.get("chat_template") if isinstance(tokenizer, dict) else None
    return template if isinstance(template, str) else None
