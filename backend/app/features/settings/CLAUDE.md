# feature: settings (persisted user/app settings)

GUI-set, restart-surviving settings kept **out** of `core/config.Settings` (which
is env-derived and treated as read-only at runtime). Backs the first-run GPU
onboarding, the Settings page, and the theme.

## Files
- `service.py` — a tiny JSON store at `data/app_settings.json` (chmod 600; same
  pattern as the HF-token file). **No torch/ML imports** — safe to read on boot.
  - Accessors used elsewhere: `selected_gpu_indices()` (the canonical GPU choice;
    read by `core/hardware.py`), `selected_gpu_index()` (legacy), `vram_override_gb()`,
    `is_onboarded()`, `get_token(name)`.
  - `public()` masks token secrets to hints; `patch()` merges (empty token = remove);
    `onboard(indices)` sets `onboarded=True` + the chosen GPU(s).
- `router.py` — `GET/PATCH /api/settings`, `POST /api/settings/onboard`.

## Stored fields
`onboarded`, `selected_gpu_indices` (list; None ⇒ largest detected GPU) with the
legacy `selected_gpu_index` mirrored on every write for back-compat (reads wrap a
lone legacy int as `[idx]` — never delete the old key), `gpu_vram_gb_override`
(None ⇒ detected VRAM), `theme` (`light|dark`), `tokens` (generic `{name: secret}`;
HF token keeps its own secure file in `features/models/service.py`).

## Gotchas
- Never return raw token secrets — `public()` only emits `{configured, hint}`.
- The hardware module reads the GPU choice from here; keep this import-light and
  free of circular imports (don't import `core/hardware` from this feature).
