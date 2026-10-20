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
| `GET` | `/api/versions/<id>/changes/` | viewer | how much each layer and module changed: `modules`, `layers[{layer, norms}]`, totals |
| `GET` | `/api/versions/<id>/exports/` | viewer | a page of the version's exports |
| `POST` | `/api/versions/<id>/exports/` | trainer | `202` an export: `lora`, `merged` or `gguf` (`out_type` f16, bf16, q8_0); `409 not_exportable` |
| `GET` | `/api/versions/exports/<id>/` | viewer | one export, with its status and where it is |
| `DELETE` | `/api/versions/exports/<id>/` | trainer | `204`; deletes its files |
| `GET` | `/api/versions/exports/<id>/download/` | viewer | the zip (`<slug>-v<n>-lora.zip`) or the GGUF file (`<slug>-v<n>-<out_type>.gguf`); `409 export_not_ready` |

## Layers

```
views.py → services/version_service.py → repositories/version_repository.py → ModelVersion
                                        └→ apps.projects ProjectRepository (the active version)
         → services/export_service.py → repositories/export_repository.py → Export
tasks.py ─┘                         └→ `python -m mesbah.export` (merged, GGUF)
```

## Classes and methods

**`ModelVersion`** — a project's version: its number (0 is the root) and name, notes, its kind
(`base`, `scratch_root`, `lora`), where its delta is stored, the LoRA settings it was trained
with (rank, alpha, rsLoRA, target modules, biases), its size on disk beside the full model's,
what changed (`delta_stats`) and how training went (`metrics`).

**`VersionRepository`** — live versions are those of a live project; a project's versions with their
child counts, its root, the next number (counting removed versions, so numbers are never reused),
versions by id, children of a version, and moving children to another parent.

**`VersionService`**, for the acting user:
- `record_trained()` — a new delta version from a finished run, numbered next.
- `tree()` — a project's versions; `describe()` one as the API shows it, with whether it is
  active and a summary of its delta.
- `create_root()` — the base version, number 0, made active; called when a project is created,
  and as a `scratch_root` (stored where the new model is) when a pretrained model is adopted.
- `activate()` — makes a version the one conversations use.
- `changes()` — the trainer's per-module norms as a grid of layers by module, for the map.
- `change()` — name and notes; `remove()` refuses the root and the active version and moves the
  children up before soft-deleting.

**`Export`** — a version in another format: `lora` (the adapter zipped with a README for vLLM
and PEFT), `merged` (full weights with the change folded in), `gguf` (one file for llama.cpp
and Ollama, beside a Modelfile); its status, where it is and its size.
**`ExportRepository`** — live exports are those of a live version and project; a version's
exports, one with its version and project loaded.

**`ExportService`** — `listing()`, `find()`, `describe()` (a merged folder is not offered as a
download: it is as large as the model), `create()` (a LoRA or merged export needs a trained
version; the task is queued after the commit), `remove()` (files too), `download()` (the file and
the name it is sent under: **`Download`**), and `run()`,
the tasks' body: zips the adapter, or writes a config and runs `mesbah.export`, then reads its
status. **`package`** / **`convert`** (`tasks.py`) — the zip on the default queue; merging and
converting on the `heavy` queue, because they load the whole model.

**`RootVersionKept`**, **`ActiveVersionKept`**, **`NotExportable`**, **`ExportNotReady`**
(`services/errors.py`) — the refusals.

## Decisions worth not re-litigating

**Every delta is measured from the base, not from the parent.** Any engine then loads one
adapter for any version, latency never grows with depth, and removing a version in the middle
of the tree breaks nothing — its children's deltas never depended on it.

**Numbers are never reused.** `v3` keeps meaning the same weights after `v2` is removed.
