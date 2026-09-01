# feature: training (frontend)

`TrainingPanel` — launch QLoRA runs and watch them **live**.

## Simple/Expert mode (`core/ui-mode.ts`)
Expert mode is the launcher and dashboard described below, unchanged. **Simple
mode** (the default) reduces both sides to what a non-technical user needs:
- Left: name field + the ready-count banner (no link, no toggles, no dataset
  picker) + one "درّب المساعد الآن 🚀" button. `useCorrections`/`onlyCorrected`
  keep their default values (`true`/`false`) — just not exposed — and the
  "إعدادات QLoRA المتقدمة" collapsible isn't rendered at all, so hardware-derived
  defaults from `project.default_train_config` always apply.
- Right: a plain status sentence (`simpleStatus()`, from `STATUS_SIMPLE_AR`) +
  the same `p-progressBar` + an approximate "N دقائق متبقية" (`etaMinutes()`,
  derived from the observed steps/sec since `watch()` started via `etaStart`) —
  no KPI cards, no loss chart, no raw terminal log.
- A `project.kind === 'scratch'` project (only reachable by having been created
  in Expert mode — see `features/projects`) shows a one-line "بدّل إلى وضع
  الخبير" notice in Simple mode instead of the from-scratch wizard-like launcher.

## Expert-mode launcher and dashboard
- Left: launcher (dataset-ready count from `api.datasetPreview`, a "راجع البيانات
  في مختبر البيانات" link that emits `(reviewData)` — the workspace switches to
  the **Data Lab** tab (`app-data-lab-panel`) so the count links to a real,
  actionable curation screen instead of the old read-only preview dialog — an
  "استخدم الردود المعتمدة" (`use_corrections`) toggle, an **HF dataset picker** —
  one shared `<ng-template #dsPicker>` (via `NgTemplateOutlet`, parameterized by
  placeholder) rendered by both the scratch and QLoRA launchers (`datasets`
  signal, `searchDs/addDs/removeDs`) — run name, "only corrected" toggle, start)
  + run history list. Start is enabled when there are corrections **or** ≥1 HF
  dataset; `start()` sends `{use_corrections, datasets:[{repo,config,split,text_field}]}`.
- Right: live dashboard — KPI cards (step, loss, lr, VRAM), `p-progressBar`, and a
  **chart.js loss curve** (`p-chart`).

## Live metrics over WebSocket
`watch(run)` opens `api.trainingSocket(runId)`; messages are `{type:'metric'|'status'}`:
- `metric` with `event:'log'` → push `(step, loss)` to the chart signal and merge
  the point into `live()` (drives the KPI cards / VRAM).
- `status` → updates the run; on a terminal status it closes the socket, refreshes
  the run + list, toasts, and emits `(changed)` so the workspace reloads the
  active-version badge.

## Notes
- Reassign `chartData.set({...})` with fresh arrays so `p-chart` re-renders.
- Starting a run with 0 examples comes back `failed` → surfaced as an error toast.
- `totalSteps()` comes from `run.progress.total_steps` **`||`** the stream value
  (`||`, not `??`: an HF-dataset-only run can start with a 0 estimate that the
  trainer corrects at `on_train_begin`); progress % = step/total.
