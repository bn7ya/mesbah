"""Project business logic.

Creating a project also seeds the **root node** of its version tree — a
``ModelVersion`` with ``is_base=True`` representing the untouched base model and
set active by default. Everything the user trains later hangs off this root.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone

from sqlalchemy import text
from sqlmodel import Session, select

from ...core import hardware
from ...core.config import settings
from ...core.models import (AutoEnhanceLoop, Message, ModelVersion, Project)
from ...core.models import Session as ChatSession
from ...core.models import Task, TrainingRun
from .schemas import ProjectCreate, ProjectUpdate


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_project(db: Session, data: ProjectCreate) -> Project:
    is_scratch = data.kind == "scratch"
    config = dict(data.default_train_config or {})
    if not config:
        config = _default_scratch_config() if is_scratch else _default_train_config()
    # Carry the architecture spec inside the train config so the trainer can read
    # it back (and so it round-trips on GET /projects/{id}).
    if data.architecture:
        config["architecture"] = data.architecture

    # A from-scratch project has no pretrained weights to download; only a real
    # fine-tune base gets the local-cache shortcut.
    local_path = data.base_model_local_path
    if not is_scratch and not local_path:
        candidate = settings.models_dir / data.base_model_repo.replace("/", "__")
        if candidate.exists() and any(candidate.iterdir()):
            local_path = str(candidate)

    project = Project(
        name=data.name,
        description=data.description,
        kind=data.kind,
        base_model_repo=data.base_model_repo,
        base_model_local_path=local_path,
        language=data.language,
        default_train_config=config,
    )
    db.add(project)
    db.flush()  # assign project.id

    # Seed the version-tree root node. For scratch this represents the randomly
    # initialized model (no adapter yet); for finetune it's the base model.
    root_label = "Init · نموذج مُهيّأ من الصفر" if is_scratch else "Base · النموذج الأساسي"
    root = ModelVersion(
        project_id=project.id,
        parent_id=None,
        label=root_label,
        notes=(f"From-scratch architecture: {data.base_model_repo}" if is_scratch
               else f"Base model: {project.base_model_repo}"),
        is_base=True,
        is_active=True,
        depth=0,
    )
    db.add(root)
    db.flush()
    project.active_version_id = root.id
    db.add(project)
    db.commit()
    db.refresh(project)

    # Build the project's on-disk home and write its metadata.json.
    _init_project_storage(project)
    return project


def _init_project_storage(project: Project) -> None:
    """Create ``projects/<id>/{versions,data}`` and write ``metadata.json``.

    Best-effort: a filesystem hiccup must not fail project creation (the DB row
    is the source of truth; the folder is recreated lazily by the trainer).
    """
    try:
        settings.ensure_project_dirs(project.id)
        meta = {
            "id": project.id,
            "name": project.name,
            "kind": project.kind,
            "base_model_repo": project.base_model_repo,
            "language": project.language,
            "architecture": project.default_train_config.get("architecture"),
            "train_config": {k: v for k, v in project.default_train_config.items()
                             if k != "architecture"},
            "created_at": project.created_at.isoformat(),
        }
        settings.project_metadata_path(project.id).write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def get_project(db: Session, project_id: str) -> Project | None:
    return db.get(Project, project_id)


def list_projects(db: Session) -> list[Project]:
    return list(db.exec(select(Project).order_by(Project.updated_at.desc())).all())


def update_project(db: Session, project: Project, data: ProjectUpdate) -> Project:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    project.updated_at = _now()
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project: Project) -> None:
    """Delete a project and everything under it (manual cascade).

    The schema has circular foreign keys (project.active_version ↔ model_version,
    model_version self-parent, training_run ↔ model_version), so we defer FK
    enforcement to commit time — by which point every related row is gone and no
    reference dangles.
    """
    db.connection().exec_driver_sql("PRAGMA defer_foreign_keys=ON")
    # Drop the project's pointer into its own version tree first.
    project.active_version_id = None
    db.add(project)
    db.flush()
    session_ids = [s.id for s in db.exec(
        select(ChatSession).where(ChatSession.project_id == project.id)
    ).all()]
    if session_ids:
        for m in db.exec(select(Message).where(Message.session_id.in_(session_ids))).all():
            db.delete(m)
    for model in (ChatSession, Task, TrainingRun, ModelVersion, AutoEnhanceLoop):
        for row in db.exec(select(model).where(model.project_id == project.id)).all():
            db.delete(row)
    db.delete(project)
    db.commit()

    # Remove the project's on-disk home (checkpoints, corpus, metadata). Best-
    # effort — the DB delete already succeeded, so a stale folder is harmless.
    try:
        shutil.rmtree(settings.project_dir(project.id), ignore_errors=True)
    except OSError:
        pass


def _default_train_config() -> dict:
    """QLoRA defaults derived from the machine's detected VRAM + RAM.

    ``core/hardware.compute_train_defaults`` picks the sequence length, micro-batch,
    grad-accum, LoRA rank, and CPU-offload budget from the real GPU/RAM (no hardcoded
    16 GB). ``MISBAH_MAX_TRAIN_SEQ_LEN`` still overrides the seq length if set. See
    ``backend/scripts/train_qlora.py`` and docs/MODEL_SELECTION.md.
    """
    hw = hardware.train_defaults("finetune")
    return {
        "epochs": 3,
        "learning_rate": 2e-4,
        "lora_r": hw["lora_r"],
        "lora_alpha": hw["lora_alpha"],     # = 2*r
        "lora_dropout": 0.0,        # Unsloth-optimized default; raise if overfitting
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj",
                            "gate_proj", "up_proj", "down_proj"],  # all linear layers
        "max_seq_len": settings.max_train_seq_len or hw["max_seq_len"],
        "per_device_batch_size": hw["per_device_batch_size"],
        "grad_accum_steps": hw["grad_accum_steps"],
        "optim": "paged_adamw_8bit",
        "lr_scheduler_type": "cosine",
        "warmup_ratio": 0.03,
        "weight_decay": 0.0,
        "gradient_checkpointing": True,
        "bf16": True,
        "load_in_4bit": True,
        "attn_implementation": "sdpa",  # newer GPUs (e.g. Blackwell sm_120) lack a flash-attn build
        "packing": False,
        "use_rslora": False,
        "neftune_noise_alpha": 5,
        "seed": 42,
        # Auto-OOM recovery: on CUDA OOM, halve max_seq_len and retry down to
        # min_seq_len, up to oom_max_retries times.
        "oom_max_retries": 4,
        "min_seq_len": 256,
    }


def _default_scratch_config() -> dict:
    """Defaults for FULL training of a from-scratch model, sized to the real GPU.

    Unlike QLoRA this trains *every* parameter, so it leans on paged training
    (weights/optimizer/activations streamed GPU→CPU→disk) by default and a paged
    8-bit optimizer to keep optimizer state off the GPU. The seq length, batch,
    grad-accum, GPU budget and CPU-offload size come from
    ``core/hardware.compute_train_defaults`` (detected VRAM + RAM). See
    ``backend/scripts/train_scratch.py``.
    """
    hw = hardware.train_defaults("scratch")
    return {
        "epochs": 1,
        "learning_rate": 3e-4,
        "lr_scheduler_type": "cosine",
        "warmup_ratio": 0.02,
        "weight_decay": 0.1,
        "max_seq_len": hw["max_seq_len"],
        "per_device_batch_size": hw["per_device_batch_size"],
        "grad_accum_steps": hw["grad_accum_steps"],
        "optim": "paged_adamw_8bit",
        "gradient_checkpointing": True,
        "bf16": True,
        "seed": 42,
        # ── embedding layer ──
        "embedding_mode": "new",            # "new" | "pretrained"
        "embedding_source_repo": None,      # HF repo to load embed weights from
        # embeddings are always trainable in from-scratch (full training).
        # ── corpus (HF dataset ingested as training text) ──
        "dataset_repo": None,
        "dataset_config": None,
        "dataset_split": "train",
        "text_field": "text",
        "max_train_samples": 5000,          # cap so a first run is tractable
        # ── GPU paged training ──
        "paged_training": True,
        "gpu_budget_gb": hw["gpu_budget_gb"],
        "cpu_offload_gb": hw["cpu_offload_gb"],
        "oom_max_retries": 3,
        "min_seq_len": 128,
    }
