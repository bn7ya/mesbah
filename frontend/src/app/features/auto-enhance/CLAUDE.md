# feature: auto-enhance (frontend · التحسين التلقائي)

`AutoEnhancePanel` — launch and watch the automated self-improvement loop **live**.
Built from the `training-panel.ts` blueprint (launcher + KPI cards + chart.js + WS).

- Left: launcher — `generations`, `turns_per_generation`, `max_correction_rounds`
  (`p-inputNumber`), four threshold **sliders** (logic/language/context/الهلوسة,
  0–10), a "use project Tasks as topics" checkbox, a collapsible advanced QLoRA
  editor (same `hyper` object as training), and Start. Below: a loops-history list.
- Right: live dashboard — KPI cards (generation/turn, phase, approved count, VRAM),
  current-scores tags, `p-progressBar`, a **scores-over-turns** `p-chart` (4 lines),
  and a **live transcript** of bubbles (ask → answer → eval scores → corrections →
  turn verdict → training dividers), assistant content via `MarkdownPipe`.

## Live updates over WebSocket
`watch(loop)` opens `api.autoEnhanceSocket(id)`; messages are `{type:'event'|'status'}`:
- `event` → routed by `data.type` (`generation_start/turn_start/ask/answer/
  evaluation/correction/turn_done/training_*/loop_done/error`) into the transcript,
  the `live()` KPIs, and the scores chart (`pushChartPoint` on `turn_done`).
- `status` → updates the loop; on a terminal status it closes the socket, refreshes
  the list + loop, toasts, and emits `(changed)` so the workspace reloads the
  active-version badge (a loop creates new versions).

## Notes
- Reassign `chartData.set({...})` / `transcript.set([...])` with fresh arrays so
  Angular/`p-chart` re-render.
- Start is disabled while a loop is running; a `409` from the backend (loop already
  running, or a training run owns the GPU) surfaces as a warn toast.
- VRAM polls `api.system()` every 3 s (cleared on destroy).
- Score tags are green/red vs the loop's thresholds (`scoreSev`).
