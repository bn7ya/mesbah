# feature: data_lab (review + curate training examples)

Before a training run starts, this is where the user gets a real look at what
will actually be fed to the model — across the whole project, not one chat
session at a time — and bulk includes/excludes examples.

## Files
- `service.py` — `list_examples` (paginated, filterable by `task_id`/
  `session_id`/`status`), `summary` (counts for the header/footer), `bulk_update`
  (bulk-PATCH `approved`/`include_in_training`).
- `router.py` — `GET /api/projects/{id}/data-lab/examples`,
  `GET /api/projects/{id}/data-lab/summary`,
  `PATCH /api/projects/{id}/data-lab/examples` (body: `DataLabBulkUpdate`).
- `schemas.py` — `DataLabExample`, `DataLabListResponse`, `DataLabSummary`,
  `DataLabBulkUpdate`/`Result`.

## No new table
There is no `TrainingExample` model. An "example" here is still just an
assistant `Message` with `approved`/`include_in_training`/`corrected` — the
same primitives `training.dataset` already used, just finally exposed as a
real cross-session, filterable, bulk-editable list instead of being reachable
only one star-click at a time inside a single chat.

## Shared predicate with `training.dataset`
`training/dataset.py` now exposes two things this feature builds on directly:
- `is_target(message, only_corrected=False)` — the "will this be used in a
  run?" predicate, extracted out of `collect_examples` so both features
  always agree on the answer.
- `iter_candidates(db, project_id, session_ids=None, task_id=None)` — every
  assistant turn in the project paired with its session and the single
  preceding user turn (a short display preview; **not** the full growing
  context `collect_examples` builds for the actual training JSONL).

`would_include` in `DataLabExample` and `would_include_count` in
`DataLabSummary` are literally `dataset.is_target(...)` — if the Data Lab
says an example will be used, the training run's dataset builder will use it
too, under the same `only_corrected` flag.

## `status`
Derived, not stored: `pending` (not yet approved), `approved` (approved +
included), `excluded` (approved but `include_in_training=False`). See
`service._status`.

## Gotchas
- `bulk_update` re-derives the caller's own candidate id set
  (`dataset.iter_candidates(db, project_id)`) and silently drops any message
  id that doesn't belong to this project — never trust ids from the request
  body against a different project's messages.
- This feature only *reads and toggles* existing `Message` flags; it never
  creates, edits the text of, or deletes messages. Inline editing, dataset
  stats/quality checks and external JSONL import were explicitly scoped out
  of this pass — see the root plan if picking those up later.
