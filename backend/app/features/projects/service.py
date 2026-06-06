"""Project business logic.

Creating a project also seeds the **root node** of its version tree — a
``ModelVersion`` with ``is_base=True`` representing the untouched base model and
set active by default. Everything the user trains later hangs off this root.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlmodel import Session, select

from ...core.config import settings
from ...core.models import (AutoEnhanceLoop, Message, ModelVersion, Project)
from ...core.models import Session as ChatSession
from ...core.models import Task, TrainingRun
from .schemas import ProjectCreate, ProjectUpdate


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_project(db: Session, data: ProjectCreate) -> Project:
    config = data.default_train_config or _default_train_config()
    # If the model is already downloaded locally, point at it so chat/training
    # never hit the network (see features/models download layout).
    local_path = data.base_model_local_path
    if not local_path:
        candidate = settings.models_dir / data.base_model_repo.replace("/", "__")
        if candidate.exists() and any(candidate.iterdir()):
            local_path = str(candidate)
    project = Project(
        name=data.name,
        description=data.description,
        base_model_repo=data.base_model_repo,
        base_model_local_path=local_path,
        language=data.language,
        default_train_config=config,
    )
    db.add(project)
    db.flush()  # assign project.id

    # Seed the version-tree root node (the base model itself).
    root = ModelVersion(
        project_id=project.id,
        parent_id=None,
        label="Base · النموذج الأساسي",
        notes=f"Base model: {project.base_model_repo}",
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
    return project


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


def _default_train_config() -> dict:
    """QLoRA defaults tuned for an 8–14B model on a 16 GB RTX 5080.

    See ``backend/scripts/train_qlora.py`` and docs/MODEL_SELECTION.md for the
    reasoning behind these numbers.
    """
    return {
        "epochs": 3,
        "learning_rate": 2e-4,
        "lora_r": 16,               # 16 for 14B, raise to 32 for 8B
        "lora_alpha": 32,           # = r or 2*r
        "lora_dropout": 0.0,        # Unsloth-optimized default; raise if overfitting
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj",
                            "gate_proj", "up_proj", "down_proj"],  # all linear layers
        "max_seq_len": settings.max_train_seq_len,
        "per_device_batch_size": 1,
        "grad_accum_steps": 16,     # effective batch 16
        "optim": "paged_adamw_8bit",
        "lr_scheduler_type": "cosine",
        "warmup_ratio": 0.03,
        "weight_decay": 0.0,
        "gradient_checkpointing": True,
        "bf16": True,
        "load_in_4bit": True,
        "attn_implementation": "sdpa",  # Blackwell sm_120: no flash-attn build
        "packing": False,
        "use_rslora": False,
        "neftune_noise_alpha": 5,
        "seed": 42,
        # Auto-OOM recovery: on CUDA OOM, halve max_seq_len and retry down to
        # min_seq_len, up to oom_max_retries times.
        "oom_max_retries": 4,
        "min_seq_len": 256,
    }
