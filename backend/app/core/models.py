"""Domain models (SQLModel ORM tables).

The whole product is four nested ideas:

    Project ──< Task
            ──< Session ──< Message
            ──< TrainingRun ──> ModelVersion (a node in the version tree)

* A **Project** wraps one HuggingFace base model and owns everything below it.
* A **Task** is an objective the model should learn to do ("answer support
  tickets in Arabic", ...). Sessions can be attached to a task.
* A **Session** is a chat. Each assistant **Message** can be *edited* by the
  user (a "correction") and *approved* — approved messages become training data.
* A **TrainingRun** is one QLoRA fine-tune. It starts from a parent
  **ModelVersion** (or the base model) and, on success, produces a new
  ModelVersion node — giving us a branchable, reversible version tree.

Tables live together on purpose: the foreign keys are circular, and keeping them
in one module sidesteps import-order pain. Feature folders own the *behaviour*
(routers + services); this module only owns the *shape* of the data.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from sqlalchemy import JSON, Column, Text
from sqlmodel import Field, SQLModel

# NOTE: We deliberately do NOT use SQLModel ``Relationship`` here. With
# ``from __future__ import annotations`` the stringified generics confuse
# SQLAlchemy's mapper, and the circular ModelVersion<->TrainingRun foreign keys
# make relationship resolution ambiguous. All access is via explicit queries in
# the feature services, and cascade deletes are handled there too.


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ─────────────────────────────────────────────────────────────────────
class MessageRole(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"


class TaskStatus(str, Enum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"


class RunStatus(str, Enum):
    pending = "pending"        # created, not yet started
    preparing = "preparing"    # building dataset / loading model
    running = "running"        # training loop active
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


# ── Project ───────────────────────────────────────────────────────────────────
class Project(SQLModel, table=True):
    __tablename__ = "projects"

    id: str = Field(default_factory=_uuid, primary_key=True)
    name: str
    description: str = Field(default="", sa_column=Column(Text))
    # HuggingFace repo id of the base model this project fine-tunes.
    base_model_repo: str
    base_model_local_path: Optional[str] = None
    # Currently selected version used for inference (None => raw base model).
    active_version_id: Optional[str] = Field(default=None, foreign_key="model_versions.id")
    # Default QLoRA hyper-parameters; copied into each new TrainingRun.
    default_train_config: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    language: str = Field(default="ar")
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


# ── Task ──────────────────────────────────────────────────────────────────────
class Task(SQLModel, table=True):
    __tablename__ = "tasks"

    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    title: str
    description: str = Field(default="", sa_column=Column(Text))
    # Free-text "what good looks like" — fed to the model as guidance.
    objective: str = Field(default="", sa_column=Column(Text))
    status: TaskStatus = Field(default=TaskStatus.todo)
    order_index: int = Field(default=0)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


# ── Session (a chat) ──────────────────────────────────────────────────────────
class Session(SQLModel, table=True):
    __tablename__ = "sessions"

    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    task_id: Optional[str] = Field(default=None, foreign_key="tasks.id", index=True)
    title: str = Field(default="جلسة جديدة")
    # Optional system prompt steering the assistant for this session.
    system_prompt: str = Field(default="", sa_column=Column(Text))
    # System prompt used when the model self-corrects a reply (the "magic wand").
    # Empty => fall back to settings.default_correction_prompt.
    correction_prompt: str = Field(default="", sa_column=Column(Text))
    # Which model version produced the answers in this chat (None => base).
    model_version_id: Optional[str] = Field(default=None, foreign_key="model_versions.id")
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


# ── Message ───────────────────────────────────────────────────────────────────
class Message(SQLModel, table=True):
    """One chat turn.

    The correction workflow lives here: ``content`` is the *current* text. When
    the user edits an assistant reply, the model's first draft is preserved in
    ``original_content`` and ``corrected`` flips True. ``approved`` marks the
    turn as a clean training example; ``include_in_training`` lets the user keep
    an example but temporarily exclude it from a run.
    """
    __tablename__ = "messages"

    id: str = Field(default_factory=_uuid, primary_key=True)
    session_id: str = Field(foreign_key="sessions.id", index=True)
    role: MessageRole
    content: str = Field(default="", sa_column=Column(Text))
    # The assistant's untouched first draft (only set once an edit happens).
    original_content: Optional[str] = Field(default=None, sa_column=Column(Text))
    corrected: bool = Field(default=False)
    approved: bool = Field(default=False)
    include_in_training: bool = Field(default=True)
    order_index: int = Field(default=0)
    token_count: Optional[int] = None
    meta: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_now)


# ── ModelVersion (node in the version tree) ───────────────────────────────────
class ModelVersion(SQLModel, table=True):
    """A node in the project's version tree.

    The root node (``is_base=True``, ``parent_id=None``) represents the untouched
    base model. Every successful TrainingRun appends a child node carrying its
    LoRA ``adapter_path``. Branching = train from any node; reversing = set an
    older node active; enhancing = train from the current node.
    """
    __tablename__ = "model_versions"

    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    parent_id: Optional[str] = Field(default=None, foreign_key="model_versions.id", index=True)
    training_run_id: Optional[str] = Field(default=None, foreign_key="training_runs.id")
    label: str
    notes: str = Field(default="", sa_column=Column(Text))
    is_base: bool = Field(default=False)
    is_active: bool = Field(default=False)
    # LoRA adapter directory (None for the base node).
    adapter_path: Optional[str] = None
    # Optional fully-merged fp16 checkpoint (None until the user exports one).
    merged_path: Optional[str] = None
    metrics: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    depth: int = Field(default=0)
    created_at: datetime = Field(default_factory=_now)


# ── TrainingRun ───────────────────────────────────────────────────────────────
class AutoEnhanceLoop(SQLModel, table=True):
    """An automated self-improvement loop (التحسين التلقائي).

    The model talks to itself: generate a topic → answer → score the answer on
    logic/language/context/factuality → self-correct until it passes → curate the
    passing turns → train a QLoRA run → activate the new version → repeat for a
    number of *generations*. Reuses :class:`RunStatus` so the frontend's
    severity/label maps work unchanged. One loop runs at a time (single GPU).
    """
    __tablename__ = "auto_enhance_loops"

    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    name: str
    status: RunStatus = Field(default=RunStatus.pending)
    # Frozen at create time (reproducible across a restart): generations,
    # turns_per_generation, thresholds{logic,language,context,factuality},
    # max_correction_rounds, topic_source, hyperparams, parent_version_id,
    # ask_prompt, eval_prompt.
    config: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    # Live cursor: {generation, turn, phase, last_scores, current_run_id}.
    progress: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    # Per-generation summary: {generations: [{generation, run_id, version_id,
    # approved, total, avg_scores}]}.
    results: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    pid: Optional[int] = None
    error: Optional[str] = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=_now)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class TrainingRun(SQLModel, table=True):
    __tablename__ = "training_runs"

    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    name: str
    # Node the fine-tune resumes from (None => fresh from base model).
    parent_version_id: Optional[str] = Field(default=None, foreign_key="model_versions.id")
    # Node produced once the run completes.
    result_version_id: Optional[str] = Field(default=None, foreign_key="model_versions.id")
    status: RunStatus = Field(default=RunStatus.pending)
    config: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    dataset_path: Optional[str] = None
    num_examples: int = Field(default=0)
    # Live progress, overwritten as the subprocess emits metrics.
    progress: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    metrics: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    log_path: Optional[str] = None
    metrics_path: Optional[str] = None
    pid: Optional[int] = None
    error: Optional[str] = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=_now)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
