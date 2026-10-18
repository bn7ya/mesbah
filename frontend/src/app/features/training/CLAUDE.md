# features/training

A project's Training tab. A run learns from the project's approved replies and from library
datasets, starting from one of the project's versions, and adds a new version that stores only
what changed (a LoRA delta). The page starts runs, shows them live and shows exactly what a run
learns from. Every signed-in user sees it; trainers and above start, stop and remove runs.

A run has a `kind`. A **LoRA run** is the one above. A **pretrain run** trains a new model from
nothing and is started from the model designer (`/architect`), never from here: it belongs to a scratch project,
learns from other projects' approved replies and library datasets, and ends with the project's
first version (v0, the whole model), which joins the library and becomes the project's base. This
feature only shows pretrain runs; it never starts one.

## Routes and guard

Children of the project frame, declared in `app.routes.ts` as the `training` tab (and listed in
`PROJECT_TABS`, `projects.tabs.training`); this feature never imports `projects`.

- `/projects/:projectId/training` — approved replies, the new-run form, the runs and the examples.
- `/projects/:projectId/training/:runId` — one run, live.

`trainingGuard` is `roleGuard('viewers')` on every route entry. The backend enforces the real rule
(`ViewersReadTrainersWrite`, `IsTrainer` for stopping); the pages hide the form and the Stop and
Remove buttons from viewers and reviewers. Pages read `projectId` and `runId` as inputs
(`paramsInheritanceStrategy: 'always'`).

## Backend counterpart

`backend/apps/training/` — `GET|POST /api/training/`, `GET /api/training/plan/`,
`GET /api/training/examples/`, `GET|DELETE /api/training/<id>/`, `POST /api/training/<id>/cancel/`,
`GET /api/training/<id>/metrics/`. Three reads belong to other apps and are the only places this
feature touches them: `GET /api/versions/` and `GET /api/versions/<id>/` (the versions to start
from, and the size of the version a LoRA run made), `GET /api/datasets/` (the ready datasets a run
can learn from, only `ready` ones) and `GET /api/projects/<id>/` (only the name, for the projects a
pretrain run learns from). `training.types.ts` mirrors the serializers; a run's `hyperparams` is
`RunHyperparams`, the LoRA keys or the pretrain ones (`warmup_ratio`, `pretrain.optim`).

Error codes with `errors.*` entries in this bundle: `nothing_to_learn`, `base_model_not_ready`
(a base still downloading, or a scratch project whose first run has not finished),
`wrong_parent`, `run_still_going`, `dataset_not_ready`. A run's own `error_code` is not an HTTP
error and resolves through `training.failure.<code>`, or `training.failure.pretrain.<code>` for the
codes whose advice differs on a new model (a smaller rank means nothing there).

The bundle also holds the glossary entries only this page needs (`loss`, `epoch`,
`learning_rate`, and `adamw_torch` and `adamw_8bit`, named by the optimizer value a run stores);
`quantization` and `rank` are the core bundle's. `<app-term>` resolves keys from every registered
bundle.

## What the pages show

- **Training page**: a card with the count of approved replies, a plain sentence of what counts
  and a way to see them (or to Chat when there are none). For trainers, **Train a new version**:
  name, start from (`mat-select` of the project's versions, the active one chosen, with a line
  on what enhancing a version means), **Learn from** (the approved-replies toggle and a multi-select
  of ready library datasets, each chosen one with an optional row limit; one line to `/datasets`
  when none is ready), whether it becomes the active version, then the settings. Simple mode: passes
  over the examples (slider 1 to 5), how much the model may change (rank 8, 16 or 64) and how
  strongly it learns (rate 1e-4, 2e-4 or 5e-4), each with its exact value and a term. Expert
  mode: every hyperparameter of `HyperparamsSerializer` with its default, validated from signals.
  Then the fit verdict for this machine (icon and words, "no GPU" in plain words) and Start, which
  goes to the run. A scratch project whose first run has not finished has no version to start from,
  so the form is replaced by one sentence saying a new version can be trained once that run has
  finished. Once the model exists the form works as it does for any project. A **Runs / Examples**
  switch below: runs as cards (status in words, progress,
  latest loss, dates, the version made, datasets, who started it; Open, Stop and Remove behind a
  confirmation), refreshed every three seconds while one is unfinished; examples as the
  conversations a run sees, the reply it learns highlighted, its thinking in a secondary block,
  "edited" marks and who approved. A pretrain run's card is titled "New model" instead of its
  seeded name, says "A new model, trained from nothing" where a LoRA card says "Started from", and
  lists the projects whose approved replies it learns from by name (a count until the names load,
  "A removed project" for one that is gone), then its datasets.
- **Run page**: the stage in words, a progress bar, time elapsed and a time-left estimate from the
  recent step rate, Stop; the result (the new version, its size against the full model and the
  final loss, or the failure in words — `error_detail` in a monospace block in Expert mode only);
  the loss chart with one plain sentence about it and the learning rate and gradient norm chart
  in Expert mode; what it learned from (examples, skipped and why, tokens, datasets); and the
  settings used. A run that ran out of memory says it shortened the examples and started again.
  A pretrain run differs in four places. Its title and first fact say it is a new model trained
  from nothing. Its stages read "Loading the tokenizer", "Building the model" and "Saving the model".
  Its result says the model joined the library and is now the project's base, shows v0 and the final
  loss with links to the project's Chat tab and to Models, and never shows the size of a change.
  What it learned from is "Approved replies from" the projects by name (each links to that project's
  Training tab), then the datasets. Settings used shows only the keys the run has: the optimizer
  (AdamW or 8-bit Adam, each with a term) beside the passes and the rate, and in Expert mode the
  warm-up share and the rest, never a LoRA rank, alpha or dropout.

## Classes and methods

**`TrainingApi`** (`data/training.api.ts`) — one method per endpoint above, plus the reads of the
versions, datasets and project names. `start()` turns a `Draft` into the request body, leaving out an
empty step limit; `versions()` and `datasets()` map the other apps' wire shapes to the few fields the
form reads, `datasets()` keeping only ready ones. `projectNames()` reads each project by id and
answers a record of id to name, leaving out a project that can no longer be read.

**`TrainingStore`** (`state/training.store.ts`), provided by the training route — the plan, the
versions and the ready datasets as `rxResource`s keyed by project, and the runs and examples as
paged signals with `loading` and `error`.
- `open()` points the store at a project, reloading everything when it is the one already open,
  since route stores outlive their page; `reloadSetup()` asks for the plan, versions and datasets again.
- `loadRuns()` and `loadExamples()` fetch a page. `watchRuns()` polls the runs every three seconds
  while any is unfinished and reloads the setup once the last one ends, since a finished run adds a
  version; the page subscribes with `takeUntilDestroyed`.
- `start()` hands back the new run or the refusal for the form to show. `stop()` and `remove()` report
  success and keep a refusal in `error`; a stopped running run is remembered in `stopping` until it
  ends, and a run's own `cancel_requested` shows a stop asked elsewhere.
- `canWrite` and `unfinished` are `computed`. `noModel` is `computed` and true once the versions have
  loaded and there are none: a scratch project whose first run has not finished. `sourceNames` is
  `computed` from a resource that reads the names of the projects the page's pretrain runs learn
  from, once each, and stays `null` until they load (or when no run needs them).

**`RunStore`** (`state/run.store.ts`), provided by the run route — one run, its metric points and
the samples the time-left estimate reads.
- `open()` points the store at a run, emptying it when it is another one; `load()` fetches the run
  and the points after the last one it has, following the pages.
- `watch()` polls the run every two seconds and ticks a one-second clock while it is unfinished, and stops
  at a terminal state; a poll fetches the run first and the points after, so a finished run always has all of them.
- `stop()` asks the run to stop; `stopping` is `computed` from that request and the run's
  `cancel_requested`, so a stop asked elsewhere shows too. The new version's size is a resource
  that loads once a LoRA run is completed; a pretrain run's version is the whole model, so it asks
  for none. `sourceNames` comes from a resource over the projects a pretrain run learns from.
- `progress`, `elapsedSeconds`, `remainingSeconds`, `reading`, `finished` and `canStop` are `computed`.

**`readLoss()`** (`state/loss-trend.ts`) — reads the loss points as falling, levelled off, rising or
too early to tell, from the means of the last two windows and their noise, with the first and latest
loss. **`secondsLeft()`**, **`formatDuration()`** (`state/pace.ts`) — the steps left over the recent step
rate, and a duration in the reader's language. **`settingsFrom()`**, **`problemsOf()`**,
**`expertChanged()`**, **`resetExpert()`** (`state/train-settings.ts`) — the plan's settings with
fallbacks, the fields out of range, and whether Expert-only settings differ from the defaults.

**`shownSettings()`**, **`settingValue()`** (`state/run-settings.ts`) — which of a run's settings the
Settings used card lists, in order and only the keys the run has (Simple mode keeps the passes, the
rate, and the rank or the optimizer), and one setting's value, the optimizer being read from
`pretrain.optim`. **`sourcesOf()`** (`state/run-sources.ts`) — pairs the projects a run learns from
with their names, `null` until the names are known and a `null` name for a project that is gone.

**`TrainingPage`** (`pages/training/`) — a lead sentence, then three sections each titled by an `h2`
over its card: what training learns from (the count), the form for trainers, and the Runs / Examples
switch. The tab carries no title of its own; the tab label already names it.
Opens the project from its `projectId` input and loads the examples when that view is chosen.

**`RunPage`** (`pages/run/`) — the live run, from its `runId` input. Builds the two charts' data and the
loss sentence in the reader's language, asks before stopping and reports it in a snack bar. Tells a
LoRA run from a pretrain run: the title, the result, the failure advice, the sources and the settings
rows each have their own wording for a new model.

**`TrainForm`** (`components/train-form/`) — the new-run section: an `h2` and its intro above the form's
card. `settings`, the chosen start version and the
chosen datasets are `linkedSignal`s over the plan, the versions and the library, so a reload with the same
values keeps what was typed. Explains why Start is unavailable, starts the run and goes to it. While the
store says there is no model it shows one sentence in place of the form, and cannot start.
**`SimpleSettings`**, **`ExpertSettings`** — the two views of the same settings, bound with `model()`.
A setting whose default is empty (Maximum steps) reads "Default: No limit." in Expert mode, and a
run's settings list says "No limit" for it.
**`RunList`**, **`RunRow`** — the runs and one run's card with Open, Stop and Remove; a pretrain run's card
swaps "Started from" for "A new model, trained from nothing" and names the projects it learns from.
**`RunStatus`** — a run's status or stage in words, drawn by the shared `<app-status>` (`prominent` on
the run page); a new model's loading and saving stages have their own words. **`VersionRef`** — "v3" and the version's name, in their own directions.
**`ExampleList`**, **`ExampleCard`** — the examples and one conversation, the reply it learns highlighted.
**`RunChart`** — a Chart.js line chart, loaded lazily, with colours read from the theme, axes in the reader's
language and mirrored in RTL, redrawn when the language or colour scheme changes.
**`trainingGuard`** (`guards/`) — viewers and above.

## Decisions worth not re-litigating

**Chart.js is imported with `import('chart.js/auto')` inside `RunChart`**, so it is a lazy chunk and the
initial bundle does not grow. Colours come from hidden swatch elements whose computed `color` resolves
`light-dark()`; a custom property read directly would still be the unresolved `light-dark(...)` text.

**The time-left estimate is the client's own.** Metrics carry no timestamps, so the store samples each poll
and divides the steps left by the recent rate; it says it is estimating until two samples have moved.

**Simple mode applies what Expert mode set.** The draft is one object; switching modes changes the controls,
not the values. Simple mode shows a note, with a reset, when Expert-only settings differ from the defaults,
and the toggles show the exact value when the rate or rank matches no preset.

**A pretrain run is shown here, never started here.** Training from nothing needs a design and creates a
project, so the model designer owns it. Here a scratch project is a project like another once its model
exists, and until then the form says so; nothing in this feature reads a project's kind.

**Project names are read one by one.** A pretrain run lists project ids, and a handful of reads of
`GET /api/projects/<id>/` is cheaper and simpler than paging the whole list; a project that fails to
read is shown as removed. The runs list and the run page each hold their own resource, since route
stores are separate.

**The separator between names is a string** (`training.runs.separator`), because the Arabic comma is
not the Latin one.

**Links are built from `projectId`**, not relative (`../chat`), so they hold wherever the routes nest.
