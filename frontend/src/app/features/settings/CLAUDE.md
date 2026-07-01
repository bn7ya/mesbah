# feature: settings (frontend)

`SettingsPage` (route `/settings`) — the central place for machine + account config.
Mirrors the backend `settings` feature + the existing `models` HF-token endpoints.

- **Hardware**: shows detected GPUs / VRAM / RAM / `max_train_seq_len` from
  `api.system()`. GPU cards are **multi-select toggles**
  (`api.updateSettings({selected_gpu_indices})`; empty selection sends `null` =
  auto/largest). Selected cards show a "مُختارة" tag; with >1 selected an
  aggregate-VRAM note explains the `device_map` sharding + transformers path.
- **HuggingFace token**: status + set/clear via `api.hfTokenStatus/setHfToken/
  clearHfToken` (moved here from `models-page`). Never displays the secret.
- **API tokens** (generic): add/remove named secrets via `api.updateSettings({tokens})`
  (empty value removes). Rendered masked (`{configured, hint}`).
- **Appearance**: light/dark buttons → toggles the `.dark` class + `localStorage`
  (same key as `app.ts`) and persists `theme` to the backend.

## First-run onboarding
Lives in the **shell** (`app.ts`/`app.html`), not here: after `api.system()`, if
`!onboarded` an overlay lists detected GPUs as **checkbox cards** with a "متابعة"
confirm calling `api.onboard(indices)` (or `null` for CPU-only). Shown once;
re-pick later from this page.
