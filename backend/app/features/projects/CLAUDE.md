# feature: projects

A **Project** wraps one HuggingFace base model and owns everything below it
(tasks, sessions, training runs, version tree).

## Files
- `router.py` — CRUD at `/api/projects`. `_to_read` adds session/task/version counts.
- `service.py` — logic. `create_project` also **seeds the version-tree root**
  (`ModelVersion is_base=True`, set active) and copies `_default_train_config()`.
- `schemas.py` — `ProjectCreate/Update/Read`.

## Key behaviours
- Creating a project must always create its base `ModelVersion` and point
  `active_version_id` at it — otherwise inference has no version to resolve.
- `_default_train_config()` holds the QLoRA defaults (r=16, alpha=32, dropout=0,
  all-linear target modules, paged_adamw_8bit, sdpa, …). Tuned for 16 GB; see
  `docs/MODEL_SELECTION.md`. Per-run overrides merge on top in the training feature.
- `delete_project` is the reference **manual cascade** (defer FKs + flush). If you
  add a new child table referencing a project, delete it here too.

## Gotchas
- Don't reintroduce ORM `Relationship` — see `backend/CLAUDE.md` "Data rules".
