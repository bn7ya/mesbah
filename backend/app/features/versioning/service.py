"""Version-tree logic.

Each ``ModelVersion`` is a node; ``parent_id`` links it to the node it was
fine-tuned from. The studio's promises map onto simple operations:

* **enhance**  → create a TrainingRun whose ``parent_version_id`` is the current
  active node (handled in the training feature); the new node becomes a child.
* **reverse**  → :func:`set_active` an older node.
* **branch**   → train from any node, not just the tip.

Deleting an interior node re-parents its children so the tree stays connected.
"""
from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from ...core.models import ModelVersion, Project, TrainingRun


def list_versions(db: Session, project_id: str) -> list[ModelVersion]:
    stmt = select(ModelVersion).where(ModelVersion.project_id == project_id).order_by(
        ModelVersion.depth, ModelVersion.created_at
    )
    return list(db.exec(stmt).all())


def build_tree(db: Session, project_id: str) -> list[dict[str, Any]]:
    """Return the version tree as nested dicts rooted at the base node(s)."""
    nodes = list_versions(db, project_id)
    by_id: dict[str, dict[str, Any]] = {}
    for n in nodes:
        by_id[n.id] = {
            **n.model_dump(),
            "children": [],
        }
    roots: list[dict[str, Any]] = []
    for n in nodes:
        node = by_id[n.id]
        if n.parent_id and n.parent_id in by_id:
            by_id[n.parent_id]["children"].append(node)
        else:
            roots.append(node)
    return roots


def create_child(
    db: Session,
    project_id: str,
    parent_id: str | None,
    *,
    label: str,
    adapter_path: str | None,
    training_run_id: str | None,
    notes: str = "",
    metrics: dict | None = None,
) -> ModelVersion:
    """Append a new node under ``parent_id`` (used by the training feature)."""
    depth = 0
    if parent_id:
        parent = db.get(ModelVersion, parent_id)
        depth = (parent.depth + 1) if parent else 0
    node = ModelVersion(
        project_id=project_id,
        parent_id=parent_id,
        label=label,
        adapter_path=adapter_path,
        training_run_id=training_run_id,
        notes=notes,
        metrics=metrics or {},
        depth=depth,
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


def set_active(db: Session, project: Project, version_id: str) -> ModelVersion:
    target = db.get(ModelVersion, version_id)
    if not target or target.project_id != project.id:
        raise ValueError("Version not found in project")
    for v in list_versions(db, project.id):
        if v.is_active and v.id != version_id:
            v.is_active = False
            db.add(v)
    target.is_active = True
    db.add(target)
    project.active_version_id = target.id
    db.add(project)
    db.commit()
    db.refresh(target)
    return target


def delete_version(db: Session, version: ModelVersion) -> None:
    """Delete a node, keeping the tree connected and no FK dangling.

    We null every *incoming* reference (project.active_version, child.parent,
    training_run.result/parent) and **flush** those updates before deleting the
    node, so by the time the DELETE runs nothing points at it.
    """
    if version.is_base:
        raise ValueError("Cannot delete the base (root) version")
    db.connection().exec_driver_sql("PRAGMA defer_foreign_keys=ON")

    # Re-parent children onto this node's parent to keep the tree connected.
    for child in db.exec(select(ModelVersion).where(ModelVersion.parent_id == version.id)).all():
        child.parent_id = version.parent_id
        db.add(child)
    # Null any training-run references to this version.
    for run in db.exec(select(TrainingRun).where(TrainingRun.result_version_id == version.id)).all():
        run.result_version_id = None
        db.add(run)
    for run in db.exec(select(TrainingRun).where(TrainingRun.parent_version_id == version.id)).all():
        run.parent_version_id = None
        db.add(run)
    # If active, fall back to the base node.
    if version.is_active:
        base = db.exec(select(ModelVersion).where(
            ModelVersion.project_id == version.project_id,
            ModelVersion.is_base == True,  # noqa: E712
        )).first()
        project = db.get(Project, version.project_id)
        if base and project:
            base.is_active = True
            project.active_version_id = base.id
            db.add(base)
            db.add(project)
    db.flush()           # persist all the reference nulling first
    db.delete(version)
    db.commit()
