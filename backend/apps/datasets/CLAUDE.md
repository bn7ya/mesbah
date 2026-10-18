# apps/datasets

The dataset library: searching HuggingFace datasets, reading how their rows would become
training rows, importing a split, uploading a file, and paging through what was saved. The
backend half of the Datasets page. Datasets are install-wide, not per project.

## Its counterpart

`frontend/src/app/features/datasets/` — the Datasets page and one dataset's page.

## The training row

Every dataset is saved as `MESBAH_DATA_DIR/datasets/<id>.jsonl`, one row per line, in the shape
the trainer reads:

```json
{"messages": [{"role": "system|user|assistant", "content": "…", "thinking": "…optional"}]}
{"text": "…"}
```

The last message is always the assistant reply to learn; `thinking` appears only on assistant
messages that have one. Beside the file, `<id>.index.json` holds the byte offset of every
hundredth line, so a page of rows is a seek and a short read.

## Endpoints

| Method | Path | Who | Returns |
|---|---|---|---|
| `GET` | `/api/datasets/` | viewer | a page of library datasets |
| `POST` | `/api/datasets/` | trainer | `202` the dataset, queued; `400 unsupported_format`, `missing_column`, `unknown_split`, `hub_dataset_gated`; `404 hub_dataset_not_found`; `502 hub_dataset_unavailable` |
| `POST` | `/api/datasets/upload/` | trainer | multipart `file` (+ `name`): `201` ready (under 5 MB) or `202` queued; `413 file_too_large`, `400 unsupported_file`, `unsupported_format`, `empty_file` |
| `GET` | `/api/datasets/<id>/` | viewer | one dataset with its progress |
| `PATCH` | `/api/datasets/<id>/` | trainer | `name`, `description` |
| `DELETE` | `/api/datasets/<id>/` | trainer | `204`; deletes the file |
| `GET` | `/api/datasets/<id>/rows/?page=&page_size=` | viewer | a page of rows as conversations; `409 dataset_not_ready` |
| `POST` | `/api/datasets/<id>/cancel/` | trainer | the dataset; the import stops at its next check |
| `POST` | `/api/datasets/<id>/retry/` | trainer | `202` the dataset, queued again; `409 upload_missing` |
| `GET` | `/api/datasets/hub/?search=` | viewer | a page of HuggingFace results; empty search = popular text-generation datasets (cached 15 minutes) |
| `GET` | `/api/datasets/hub/inspect/?repo=&config=&split=&prompt=&reply=&thinking=` | viewer | subsets and splits with row counts, the columns, the detected layout, the mapping in use and the first rows as conversations |

A failed import records `error_code`: `gated`, `not_found`, `hf_unreachable`,
`unsupported_format`, `disk_full` or `failed`.

## Layouts

`services/formats.py` detects one from the column names and the first rows, in this order:

| Layout | Columns |
|---|---|
| `messages` | `messages` (or `conversation`, `chat`, `dialog`…) holding `{role, content}` turns, maybe with `thinking`, `reasoning_content` or `reasoning` |
| `sharegpt` | `conversations` holding `{from: human\|gpt\|system, value}` |
| `instruction` | `instruction` [+ `input`] and `output` or `response` |
| `prompt_completion` | `prompt`+`completion`, `prompt`+`response`, `question`+`answer`, `query`+`response`; either side may be a string or a list of turns |
| `text` | `text` |
| `unsupported` | anything else, `chosen`/`rejected` preference pairs included |

A `system` column opens the conversation. A `reasoning`, `thinking`, `reasoning_content`,
`think` or `cot` column becomes the last reply's thinking; otherwise a reply that starts with
`<think>…</think>` (or holds only the closing tag) is split. Column names match without case,
and a CSV cell holding JSON is read as JSON. A row that does not map (no reply, an unknown
speaker, an empty turn) is skipped and counted.

## Layers

```
views/ → services/dataset_service.py → repositories/dataset_repository.py → Dataset
               ├→ services/hub_client.py (HfApi + datasets-server, with the saved token)
               ├→ services/formats.py (detect, normalise, split thinking)
               ├→ services/storage.py (paths, the JSONL writer and reader, upload readers)
               └→ tasks.py → services/import_service.py
```

Permissions come from `apps.members.permissions` (`ViewersReadTrainersWrite`, `IsTrainer`,
`IsViewer`); the app has no rules of its own beyond them.

## Classes and methods

**`Dataset`** (`models.py`) — a library entry: its name and description, where it came from
(a HuggingFace repo, subset, split and revision, or an uploaded file name), the column mapping
and layout, the row limit and the source's row count, the import's state, progress and error
code, and the result (rows, skipped, size, sha256, whether any row has thinking, a five-row
preview, the file path), plus the cancel flag.

**`DatasetRepository`** — the library newest first with its authors, which repos are already
imported, whether an import should stop (cancelled or removed), and the progress an import
writes while it runs.

**`ColumnMap`** (`services/formats.py`) — which column plays which part (conversation, system,
prompt, input, reply, thinking, text) for one layout; `required()` and `columns()` list the
columns it reads. **`detect()`** picks the layout, **`chosen()`** builds a prompt/reply mapping
from columns a person picked, **`normalise()`** turns one row into the training row or `None`,
**`sample()`** normalises a few rows and counts the misses (a reply's `<think>` block is split
with `mesbah.think`), **`has_thinking()`**, **`column_map()`** and **`decoded()`** are the
helpers around them.

**`DatasetsHub`** (`services/hub_client.py`) — HuggingFace for datasets: `search()` (by
downloads; an empty search lists popular text-generation datasets), `describe()` (licence,
size, languages, gated, a description snippet, the revision), `splits()` with row counts,
`first_rows()`, `parquet_files()` for one split, and `download()` streaming a file while asking
whether to go on. Turns failures into `hub_dataset_not_found`, `hub_dataset_gated`,
`hub_dataset_unavailable` and `hf_unreachable`.

**`JsonlWriter`** (`services/storage.py`) — writes training rows to a `.part` file with a
running sha256 and the line index, then `commit()`s it into place or `discard()`s it.
**`JsonlRows`** — a saved dataset as a sliceable sequence, read by line offset, so DRF's
paginator pages it. **`read_upload()`**, **`peek_upload()`**, **`upload_columns()`** and
**`parquet_batches()`** read JSONL, JSON, CSV and parquet rows; the path helpers say where
everything lives.

**`DatasetService`**, for the acting user:
- `search()`, `featured()` — HuggingFace results with whether each repo is in the library.
- `inspect()` — the subsets and splits, the columns, the detected layout, the mapping in use
  (detected, or the chosen prompt/reply/thinking columns) and the first rows normalised.
- `start_import()` — checks the split and the mapping against the first rows, records the
  dataset and queues the import.
- `upload()` — refuses the wrong type or a file over 200 MB, stages the file, checks its layout,
  then reads it at once (under 5 MB) or queues it.
- `update()`, `rows()`, `cancel()`, `retry()`, `remove()` (soft-deletes and deletes the files),
  `find()`, `library()`, `describe()` — one dataset as the API shows it, with an excerpt of its
  first row.

**`ImportService.run()`** — the task body: downloads the split's parquet files one at a time (or
reads the staged upload), normalises rows in batches, stops at the limit, saves progress every
second, checks the cancel flag between batches and while downloading, and settles the dataset
as ready, failed (with a code) or cancelled.

**`import_dataset`** (`tasks.py`) — the Celery task `datasets.import` on the `default` queue.

## Decisions worth not re-litigating

**Rows come from the datasets-server's parquet copy.** It exists for every public dataset the
viewer can show, in one format, per split, so the import never runs a dataset's loading script
and needs no `datasets` package. A dataset without that copy is `hub_dataset_unavailable`.

**One shard at a time.** A row limit of 10 000 should not download a 20 GB split; the import
stops downloading once it has the rows.

**A gated dataset is a 400, not a 403.** The frontend's error interceptor reads 401 and 403 as
a lost session and sends the user to sign in.

**Uploads keep their staged file until the import succeeds**, so a failed or cancelled upload
can be tried again; `remove()` deletes it.
