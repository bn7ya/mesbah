# features/models

The Models page: the library of models downloaded to this machine, and a search of
HuggingFace to add more. Every signed-in user sees it; trainers and above add, stop, retry and
remove.

## Route and guard

`/models`. `modelsGuard` is `roleGuard('viewers')`; the backend enforces the real rule
(`IsViewer` to read, `IsTrainer` to write). The page hides the write buttons from viewers and
reviewers (`ModelsStore.canWrite`). The menu lists it before System.

## Backend counterpart

`backend/apps/models/` — `GET|POST /api/models/`, `GET|DELETE /api/models/<id>/`,
`POST /api/models/<id>/cancel/` and `.../retry/`, `GET /api/models/hub/` (popular models, or a
search with `search` and `task`), `GET /api/models/hub/inspect/?repo=`. `models.types.ts`
mirrors the serializers, the page envelope included.

## What the page shows

- **Library**: one outlined card per model, newest first — repo id, parameters, the family in
  words, a Thinking marker, and its state: waiting or downloading (a progress bar and
  "done of total", with Cancel), ready (with its size), failed (the reason from `error_code`,
  with Try again; a gated model links to the System page for a token) or stopped (Try again).
  Remove asks first. An empty library says so, with what a reader may do about it.
- **Find a model**: a search field (Enter or the search button) and a Text generation / Text
  to text toggle. An empty search lists the popular models, and the toggle is disabled until
  there is text. Results are cards: downloads and likes, parameters, license, a lock when gated,
  Thinking, how chat would fit, "In library", and Details.
- **Details dialog**: the architecture in plain words, then whether the model fits this
  machine for compressed chat, full-precision chat and QLoRA training, then Download.

## Classes and methods

**`ModelsApi`** (`data/models.api.ts`) — one method per endpoint. `hub()` sends no parameters
for an empty search, which is how the backend lists popular models.

**`ModelsStore`** (`state/models.store.ts`), provided by the route — the library page,
`pageIndex`, `pageSize`, `loading`, `error`, `working` (ids of rows mid-request) and `adding`
as signals; the HuggingFace search and the inspected model are `rxResource`s behind
`hubResults`, `hubLoading`, `hubError`, `inspection`, `inspecting` and `inspectionError`.
- `canWrite` and `downloading` are `computed`.
- `load()` fetches a library page and reports a failure; `add()` queues a download, reloads
  the first page and the search, and hands a refusal back to the dialog.
- `cancel()`, `retry()` and `remove()` change one row and keep the failure in `error`.
- `watchDownloads()` is a stream the page subscribes to: every two seconds while a row is
  queued or downloading, it refreshes the library quietly, and it goes silent when none is.
- `search()`, `searchAgain()`, `inspect()`, `inspectAgain()` and `stopInspecting()` drive the
  two resources.

**`ModelsPage`** (`pages/models/`) — the page above. Keeps the search text and the task as
signals, subscribes to `watchDownloads()` until it is destroyed, opens the details dialog with
its own injector, asks before removing and reports each change in a snack bar.

**`ModelDetailsDialog`** (`dialogs/model-details/`) — loads the inspection through the store
and forgets it on close. Download is disabled, with the reason beside it, when the repository
has no weights, the model is already in the library (a failed or stopped one can be downloaded
again), or the reader cannot write. Closes with `true` once the download is queued.

**`modelsGuard`** (`guards/`) — viewers and above.

## Errors

Removing a model a project is built on answers `409 model_in_use`; `errors.model_in_use` in this
bundle says so in the reader's language and the page shows it in its alert.

## Decisions worth not re-litigating

**Polling is a stream the page owns, not an effect in the store.** The page subscribes with
`takeUntilDestroyed()`, so leaving the page cancels the timer and any request in flight.

**A background refresh never shows an error.** A failed poll keeps the last list; the next
tick tries again.

**Counts follow `label: n`.** "Parameters: 8.2B", never "8.2B parameters", so the Arabic has
no plural to get wrong; `{done} of {total}` is the other allowed form.
