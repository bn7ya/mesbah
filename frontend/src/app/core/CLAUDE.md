# core (frontend)

Shared, feature-agnostic glue.

- `api.ts` — the **single** typed gateway to the backend (`Api`, providedIn root).
  HTTP methods per feature + `trainingSocket(runId)` for the live WS. `API_BASE`
  is `/api` (dev proxy → :8077); `WS_BASE` derives the ws:// origin.
- `types.ts` — TypeScript interfaces mirroring `backend/app/core/models.py` +
  schemas. Field names match the API exactly (English).
- `ui-mode.ts` — `UiModeService` (providedIn root): the app-wide Simple/Expert
  mode signal, persisted via `AppSettings.ui_mode`. `load()` once at boot
  (`app.ts`), then inject anywhere and read `isSimple()` to gate
  advanced/technical UI. `set()`/`toggle()` update optimistically and PATCH
  `/api/settings`.
- `model-fit-badge.ts` — `ModelFitBadge`, a tiny shared "does this fit my GPU"
  badge for a `HubModel.fit` verdict (`[fit]` input). Reused by the
  project-creation model picker and the models page — same data, same visual.

When you add a backend endpoint, add a method here and (if it returns a new shape)
a type in `types.ts`. Keep both in sync with the backend schemas.
