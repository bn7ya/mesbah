# features/datasets

The Datasets page: the library of training data on this machine, uploading a file, and a search
of HuggingFace to import more; and one dataset's page, its rows shown as the conversations the
trainer will read. Every signed-in user sees both; trainers and above import, upload, rename,
cancel, retry and remove.

## Routes and guard

`/datasets` and `/datasets/:id`. `datasetsGuard` is `roleGuard('viewers')`, on the parent and on
each child; the backend enforces the real rule (`IsViewer` to read, `IsTrainer` to write). The
pages hide the write controls below trainers (`DatasetsStore.canWrite`). The parent route
provides one `DatasetsStore` for both pages. The menu lists Datasets after Models
(`fa-database`).

## Backend counterpart

`backend/apps/datasets/` — `GET|POST /api/datasets/`, `POST /api/datasets/upload/`,
`GET|PATCH|DELETE /api/datasets/<id>/`, `GET /api/datasets/<id>/rows/`,
`POST /api/datasets/<id>/cancel/` and `.../retry/`, `GET /api/datasets/hub/` (popular datasets,
or a search) and `GET /api/datasets/hub/inspect/`. `datasets.types.ts` mirrors the serializers,
the page envelope included. Feature error codes (`hub_dataset_*`, `unsupported_format`,
`file_too_large`…) have their text under `errors.*` in this feature's bundles.

## What the pages show

- **Library**: one outlined card per dataset, newest first — the name (a link once ready), where
  it came from (subset · split, or the file name), the description, an excerpt of the first
  row, the layout, a Thinking marker and who added it; then its state: waiting, importing (a
  bar and "Rows: done of target", the target being the smaller of the limit and the split's
  size), ready (rows, skipped, size), failed (the reason from `error_code`, with a token link
  for a gated one) or stopped. View rows, Cancel, Try again and Remove (asks first).
- **Upload a file**: the accepted types and the 200 MB limit, an optional name, a filled
  button that opens a hidden file input, upload progress from `reportProgress`, and the accepted
  layouts in an expansion panel. A file over the limit is refused before it is sent.
- **Find a dataset**: a search field; an empty search lists popular text-generation datasets.
  Cards show downloads and likes, a description, the size range in words, the languages by
  name in the reader's language, the licence, a lock when gated, "In library", and Preview.
- **Preview dialog**: the subset and split selects (with row counts), the detected layout in
  words with the columns it reads, the column list, a "Choose the columns by hand" toggle (shown
  on when nothing was recognised) with a select each for prompt, reply and thinking, the first
  rows rendered as conversations, the row limit (10 000 by default, up to 1 000 000), and
  Import. Import is disabled, with the reason beside it, until a layout is chosen and at least
  one of the first rows can be used.
- **Dataset page**: back to the list, the name and description (Edit, Remove), the facts
  (source, subset, split, layout, rows, skipped, size, thinking, added by and on; the columns
  used and the checksum in Expert mode), then the rows ten at a time with a paginator. While the
  import runs it shows the progress and refreshes until the rows are ready.

## Classes and methods

**`DatasetsApi`** (`data/datasets.api.ts`) — one method per endpoint. `hub()` sends no
parameters for an empty search; `inspect()` sends only the parts of the query that are set;
`upload()` posts a `FormData` and reports progress events.

**`DatasetsStore`** (`state/datasets.store.ts`), provided by the parent route:
- The library page, `pageIndex`, `pageSize`, `loading`, `loadError` (the library could not be
  loaded; the page offers Try again), `error` (a refused change), `working` (ids mid-request),
  `importing` and `uploadProgress` as signals; `canWrite`, `busy`, `uploading` and `openedBusy`
  are `computed`.
- The HuggingFace search and the inspected dataset are `rxResource`s behind `hubResults`,
  `hubLoading`, `hubError`, `inspection`, `inspecting` and `inspectionError`; `search()`,
  `searchAgain()`, `inspect()`, `inspectAgain()` and `stopInspecting()` drive them.
- `load()` fetches a library page and reports a failure; `watchImports()` is a stream the page
  subscribes to that refreshes the library every two seconds while an import is queued or
  running and goes quiet when none is.
- `startImport()` and `upload()` add a dataset, reload the first page and hand a refusal back
  to the caller; `cancel()`, `retry()`, `remove()` and `update()` change one dataset.
- `open()` loads one dataset and, once ready, its first page of rows; `loadRows()` turns the
  rows page; `watchOpened()` refreshes an opened dataset every two seconds while it imports and
  loads its rows when it is ready.

**`DatasetsPage`** (`pages/datasets/`) — the Datasets page above. Keeps the search text, the
upload name and an upload refusal as signals, subscribes to `watchImports()` until destroyed,
opens the preview dialog with its own injector, asks before removing, turns a HuggingFace size
category into a range, and reports each change in a snack bar.

**`DatasetPage`** (`pages/dataset/`) — one dataset by its `id` route input: opens it through the
store, subscribes to `watchOpened()`, opens the edit dialog, asks before removing and returns to
the list, and formats the date in the reader's language with Latin digits.

**`DatasetInspectDialog`** (`dialogs/dataset-inspect/`) — loads the inspection through the store
and forgets it on close; keeps showing the last inspection while a new one loads; re-inspects
when the subset, split or a chosen column changes; validates the row limit; closes with `true`
once the import is queued.

**`DatasetEditDialog`** (`dialogs/dataset-edit/`) — the name (required) and the description;
saves through the store and closes with `true`.

**`DatasetConversation`** (`components/conversation/`) — one row as chat bubbles: the system
prompt across the width, prompts at the inline end, replies at the inline start, each reply's
thinking in a collapsed expansion panel, plain text rows as one block; every text in its own
direction.

**`LanguagesPipe`** (`pipes/languages.pipe.ts`) — language codes as their names in the reader's
language, joined as a list ("Arabic and English").

**`datasetsGuard`** (`guards/`) — viewers and above.

## Decisions worth not re-litigating

**Prompt and Reply are the words for the two sides of a conversation**, in the mapping selects
and on the bubbles alike, so a column chosen as the prompt is visibly what becomes the prompt.

**Polling is a stream the page owns, not an effect in the store** (as on the Models page);
leaving the page cancels the timer, and a failed background refresh keeps the last list.

**Counts follow `label: n`** — "Rows: 200", "Rows: 1K to 10K", never "200 rows".

**Upload sits above the search.** The search lists up to 24 cards; the upload is one short card
and would otherwise be found only at the bottom of the page.
