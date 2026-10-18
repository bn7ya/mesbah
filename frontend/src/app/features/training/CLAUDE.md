# features/training

A project's Training tab. A run learns from the project's approved replies and from library
datasets, starting from one of the project's versions, and adds a new version that stores only
what changed (a LoRA delta). The page starts runs, shows them live and shows exactly what a run
learns from. Every signed-in user sees it; trainers and above start, stop and remove runs.

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
`GET /api/training/<id>/metrics/`. Two reads belong to other apps and are the only places this
feature touches them: `GET /api/versions/` and `GET /api/versions/<id>/` (the versions to start
from, and the size of the version a run made) and `GET /api/datasets/` (the ready datasets a run
can learn from, only `ready` ones). `training.types.ts` mirrors the serializers.

Error codes with `errors.*` entries in this bundle: `nothing_to_learn`, `base_model_not_ready`,
`wrong_parent`, `run_still_going`, `dataset_not_ready`. A run's own `error_code` is not an HTTP
error and resolves through `training.failure.<code>`.

The bundle also holds the glossary entries only this page needs (`loss`, `epoch`,
`learning_rate`); `quantization` and `rank` are the core bundle's. `<app-term>` resolves keys from
every registered bundle.

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
  goes to the run. A **Runs / Examples** switch below: runs as cards (status in words, progress,
  latest loss, dates, the version made, datasets, who started it; Open, Stop and Remove behind a
  confirmation), refreshed every three seconds while one is unfinished; examples as the
  conversations a run sees, the reply it learns highlighted, its thinking in a secondary block,
  "corrected" marks and who approved.
- **Run page**: the stage in words, a progress bar, time elapsed and a time-left estimate from the
  recent step rate, Stop; the result (the new version, its size against the full model and the
  final loss, or the failure in words — `error_detail` in a monospace block in Expert mode only);
  the loss chart with one plain sentence about it and the learning rate and gradient norm chart
  in Expert mode; what it learned from (examples, skipped and why, tokens, datasets); and the
  settings used. A run that ran out of memory says it shortened the examples and started again.

## Classes and methods

**`TrainingApi`** (`data/training.api.ts`) — one method per endpoint above, plus the reads of the
versions and datasets. `start()` turns a `Draft` into the request body, leaving out an empty
step limit; `versions()` and `datasets()` map the other apps' wire shapes to the few fields the
form reads, `datasets()` keeping only ready ones.

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
- `canWrite` and `unfinished` are `computed`.

**`RunStore`** (`state/run.store.ts`), provided by the run route — one run, its metric points and
the samples the time-left estimate reads.
- `open()` points the store at a run, emptying it when it is another one; `load()` fetches the run
  and the points after the last one it has, following the pages.
- `watch()` polls the run every two seconds and ticks a one-second clock while it is unfinished, and stops
  at a terminal state; a poll fetches the run first and the points after, so a finished run always has all of them.
- `stop()` asks the run to stop; `stopping` is `computed` from that request and the run's
  `cancel_requested`, so a stop asked elsewhere shows too. The new version's size is a resource
  that loads once the run is completed.
- `progress`, `elapsedSeconds`, `remainingSeconds`, `reading`, `finished` and `canStop` are `computed`.

**`readLoss()`** (`state/loss-trend.ts`) — reads the loss points as falling, levelled off, rising or
too early to tell, from the means of the last two windows and their noise, with the first and latest
loss. **`secondsLeft()`**, **`formatDuration()`** (`state/pace.ts`) — the steps left over the recent step
rate, and a duration in the reader's language. **`settingsFrom()`**, **`problemsOf()`**,
**`expertChanged()`**, **`resetExpert()`** (`state/train-settings.ts`) — the plan's settings with
fallbacks, the fields out of range, and whether Expert-only settings differ from the defaults.

**`TrainingPage`** (`pages/training/`) — the count card, the form for trainers, the Runs / Examples switch.
Opens the project from its `projectId` input and loads the examples when that view is chosen.

**`RunPage`** (`pages/run/`) — the live run, from its `runId` input. Builds the two charts' data and the
loss sentence in the reader's language, asks before stopping and reports it in a snack bar.

**`TrainForm`** (`components/train-form/`) — the new-run form. `settings`, the chosen start version and the
chosen datasets are `linkedSignal`s over the plan, the versions and the library, so a reload with the same
values keeps what was typed. Explains why Start is unavailable, starts the run and goes to it.
**`SimpleSettings`**, **`ExpertSettings`** — the two views of the same settings, bound with `model()`.
**`RunList`**, **`RunRow`** — the runs and one run's card with Open, Stop and Remove. **`RunStatus`** — a run's
status or stage in words, with an icon. **`VersionRef`** — "v3" and the version's name, in their own directions.
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

**Links are built from `projectId`**, not relative (`../chat`), so they hold wherever the routes nest.
