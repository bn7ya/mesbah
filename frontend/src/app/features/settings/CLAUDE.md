# feature: settings (frontend)

`SettingsPage` (route `/settings`) — the central place for machine + account config.
Mirrors the backend `settings` feature + the existing `models` HF-token endpoints.

- **Hardware**: shows detected GPUs / VRAM / RAM / `max_train_seq_len` from
  `api.system()`, and lets the user re-pick the training GPU
  (`api.updateSettings({selected_gpu_index})`). The selected card shows a "مُختارة" tag.
- **HuggingFace token**: status + set/clear via `api.hfTokenStatus/setHfToken/
  clearHfToken` (moved here from `models-page`). Never displays the secret.
- **API tokens** (generic): add/remove named secrets via `api.updateSettings({tokens})`
  (empty value removes). Rendered masked (`{configured, hint}`).
- **Appearance**: light/dark buttons → toggles the `.dark` class + `localStorage`
  (same key as `app.ts`) and persists `theme` to the backend.

## First-run onboarding
Lives in the **shell** (`app.ts`/`app.html`), not here: after `api.system()`, if
`!onboarded` an overlay lists detected GPUs and calls `api.onboard(index)` (or
`null` for CPU-only). Shown once; re-pick later from this page.
