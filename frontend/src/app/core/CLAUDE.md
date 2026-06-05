# core (frontend)

Shared, feature-agnostic glue.

- `api.ts` — the **single** typed gateway to the backend (`Api`, providedIn root).
  HTTP methods per feature + `trainingSocket(runId)` for the live WS. `API_BASE`
  is `/api` (dev proxy → :8077); `WS_BASE` derives the ws:// origin.
- `types.ts` — TypeScript interfaces mirroring `backend/app/core/models.py` +
  schemas. Field names match the API exactly (English).

When you add a backend endpoint, add a method here and (if it returns a new shape)
a type in `types.ts`. Keep both in sync with the backend schemas.
