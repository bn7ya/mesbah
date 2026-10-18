# apps/models

The model library: searching HuggingFace, explaining what a model is and whether it fits this
machine, and downloading it. The backend half of the Models page.

## Its counterpart

`frontend/src/app/features/models/` — the Models page.

## Endpoints

| Method | Path | Who | Returns |
|---|---|---|---|
| `GET` | `/api/models/` | viewer | a page of library models |
| `POST` | `/api/models/` | trainer | `202` the model, queued; `409 already_in_library`, `400 not_downloadable`, `507 disk_full` |
| `GET` | `/api/models/<id>/` | viewer | one library model with its progress |
| `DELETE` | `/api/models/<id>/` | trainer | `204`; deletes the downloaded files |
| `POST` | `/api/models/<id>/cancel/` | trainer | the model; the download stops on its next check |
| `POST` | `/api/models/<id>/retry/` | trainer | `202` the model, queued again |
| `GET` | `/api/models/hub/?search=&task=` | viewer | a page of HuggingFace results; empty search = popular models (cached 15 minutes) |
| `GET` | `/api/models/hub/inspect/?repo=` | viewer | the architecture, the download size and the fit; `404 hub_model_not_found`, `503 hf_unreachable` |

Every result carries `fit`: for `chat` (4-bit), `chat_full` (half precision) and `training`
(QLoRA), a `verdict` (`fits`, `tight`, `too_large`, `cpu_only`, `unknown`), the bytes it needs
and the VRAM Mesbah can use (`apps.system`).

## Layers

```
views.py → services/model_service.py → repositories/hub_model_repository.py → HubModel
                 ├→ services/hub_client.py (HfApi, with the saved token)
                 └→ tasks.py → services/download_service.py → `python -m mesbah.download` (a subprocess)
```

## Classes and methods

**`HubModel`** — a model in the library: its repo id and revision, what it is (family, type,
architecture, parameters, active parameters for MoE, licence, gated, thinking support), its
files and size, and the download's state, progress and error.

**`HubModelRepository`** — the library newest first, lookups by repo id, the cancel flag and
progress updates a download writes while it runs.

**`HubClient`** — HuggingFace, through `HfApi` with the token from `apps.system`: `search()`
(sorted by downloads, with the chat template's thinking support read from the result) and
`detail()` (model info, the file list with sizes, and `config.json`). Turns HuggingFace failures
into `hub_model_not_found` and `hf_unreachable`.

**`ModelService`**, for the acting user:
- `search()`, `featured()` — results with their fit and whether they are in the library.
- `inspect()` — the architecture in plain fields (`mesbah.sizing`), download size and fit.
- `add()` — checks weights exist and the disk has room, records the model and queues the
  download; a failed or stopped model is queued again instead.
- `cancel()`, `retry()`, `remove()` (soft-deletes the row and deletes the files).
- `describe()` — one library row as the API shows it.

**`DownloadService.run()`** — the download task's body: runs `mesbah.download` in a subprocess
with the token in its environment, records the bytes on disk every two seconds, stops the
subprocess when the cancel flag is set, and settles the row as ready (with its local path),
failed (with a reason code) or cancelled.

**`download_model`** (`tasks.py`) — the Celery task on the `default` queue.

## Decisions worth not re-litigating

**The download runs in a subprocess.** HuggingFace's client cannot be interrupted mid-file; a
process can. It also keeps hf_xet's threads out of the worker.

**Only safetensors are fetched when a repo has them.** `.bin`, `.gguf`, ONNX and `original/`
copies double the download for nothing Mesbah loads.

**Fit is an estimate, said as one.** 4-bit weights at ~0.56 bytes per parameter plus runtime
overhead; QLoRA at ~0.62 bytes per parameter plus 4 GB for activations and the optimiser. The
page says "about".
