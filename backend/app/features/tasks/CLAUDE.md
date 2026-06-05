# feature: tasks

A **Task** is an objective the model should learn within a project ("answer
support tickets in Arabic", …). Sessions can attach to a task (`Session.task_id`).

## Files
- `router.py` — CRUD nested under `/api/projects/{project_id}/tasks`. Inline
  Pydantic `TaskCreate/Update`; the ORM `Task` is returned directly.

## Notes
- `objective` is free-text "what good looks like"; the training feature can filter
  a dataset by `task_id`.
- `status` ∈ `todo | in_progress | done`; `order_index` allows manual ordering.
- Smallest feature — no `service.py`; logic lives in the router.
