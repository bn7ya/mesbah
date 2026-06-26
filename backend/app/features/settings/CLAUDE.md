# feature: settings (persisted user/app settings)

GUI-set, restart-surviving settings kept **out** of `core/config.Settings` (which
is env-derived and treated as read-only at runtime). Backs the first-run GPU
onboarding, the Settings page, and the theme.

## Files
- `service.py` — a tiny JSON store at `data/app_settings.json` (chmod 600; same
  pattern as the HF-token file). **No torch/ML imports** — safe to read on boot.
  - Accessors used elsewhere: `selected_gpu_index()`, `vram_override_gb()`,
    `is_onboarded()`, `get_token(name)` (read by `core/hardware.py`).
  - `public()` masks token secrets to hints; `patch()` merges (empty token = remove);
    `onboard(idx)` sets `onboarded=True` + the chosen GPU.
- `router.py` — `GET/PATCH /api/settings`, `POST /api/settings/onboard`.

## Stored fields
`onboarded`, `selected_gpu_index` (None ⇒ largest detected GPU),
`gpu_vram_gb_override` (None ⇒ detected VRAM), `theme` (`light|dark`),
`tokens` (generic `{name: secret}`; HF token keeps its own secure file in
`features/models/service.py`).

## Gotchas
- Never return raw token secrets — `public()` only emits `{configured, hint}`.
- The hardware module reads the GPU choice from here; keep this import-light and
  free of circular imports (don't import `core/hardware` from this feature).
