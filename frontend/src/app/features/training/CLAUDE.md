# feature: training (frontend)

`TrainingPanel` — launch QLoRA runs and watch them **live**.

- Left: launcher (dataset-ready count from `api.datasetPreview`, run name,
  "only corrected" toggle, start) + run history list.
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
- `totalSteps()` comes from `run.progress.total_steps` (or the stream); progress %
  = step/total.
