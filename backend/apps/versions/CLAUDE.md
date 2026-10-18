# apps/versions

The version tree of a project. A version is never a checkpoint: the root is the base model
itself, and every other version is one LoRA delta measured from the base (ADR-004). The parent
link records where a version was trained from. The backend half of the version tree.

## Its counterpart

`frontend/src/app/features/versions/` — the version tree on a project's page.

## Endpoints

| Method | Path | Who | Returns |
|---|---|---|---|
| `GET` | `/api/versions/?project=<id>` | viewer | a page of the project's versions, oldest first; each names `parent_id` |
| `GET` | `/api/versions/<id>/` | viewer | one version |
| `PATCH` | `/api/versions/<id>/` | trainer | the version; name and notes |
| `DELETE` | `/api/versions/<id>/` | trainer | `204`; its children move up to its parent; `409 root_version_kept`, `409 active_version_kept` |
| `POST` | `/api/versions/<id>/activate/` | trainer | the version, now active — rolling back is activating an older one |

## Layers

```
views.py → services/version_service.py → repositories/version_repository.py → ModelVersion
                                        └→ apps.projects ProjectRepository (the active version)
```

## Classes and methods

**`ModelVersion`** — a project's version: its number (0 is the root) and name, notes, its kind
(`base`, `scratch_root`, `lora`), where its delta is stored, the LoRA settings it was trained
with (rank, alpha, rsLoRA, target modules, biases), its size on disk beside the full model's,
what changed (`delta_stats`) and how training went (`metrics`).

**`VersionRepository`** — a project's versions with their child counts, its root, the next
number (counting removed versions, so numbers are never reused), versions by id, children of a
version, and moving children to another parent.

**`VersionService`**, for the acting user:
- `tree()` — a project's versions; `describe()` one as the API shows it, with whether it is
  active and a summary of its delta.
- `create_root()` — the base version, number 0, made active; called when a project is created.
- `activate()` — makes a version the one conversations use.
- `change()` — name and notes; `remove()` refuses the root and the active version and moves the
  children up before soft-deleting.

**`RootVersionKept`**, **`ActiveVersionKept`** (`services/errors.py`) — the two refusals.

## Decisions worth not re-litigating

**Every delta is measured from the base, not from the parent.** Any engine then loads one
adapter for any version, latency never grows with depth, and removing a version in the middle
of the tree breaks nothing — its children's deltas never depended on it.

**Numbers are never reused.** `v3` keeps meaning the same weights after `v2` is removed.
