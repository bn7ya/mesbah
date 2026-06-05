# feature: models (HuggingFace registry)

Discover, curate, and download base models.

## Files
- `router.py` — `/api/models/curated|search|local|download|download/status`.
- `service.py` — curated list, HF search, local registry, background downloads.

## Behaviours
- `CURATED_MODELS` is the hand-picked list shown in the new-project picker
  (Qwen3-14B recommended, Qwen3-8B, DeepSeek-R1-0528-Qwen3-8B, ALLaM/Yehia Arabic
  specialists). Each entry carries `default_seq_len` / `default_lora_r` hints. Keep
  it in sync with `docs/MODEL_SELECTION.md`.
- `search` uses `huggingface_hub.HfApi.list_models`; falls back to filtering the
  curated list when the hub is unreachable (offline-friendly).
- `DownloadManager` runs `snapshot_download` on a background thread; `status()`
  reports **bytes-on-disk** so the GUI can animate a progress bar. A 14B model is
  ~28 GB → downloads are long; status survives restarts by scanning the dir.

## Gotchas
- Local models live in `data/models/<repo__with__double__underscore>`; the path
  encoding (`/` → `__`) is shared between `start` and `status`.
- All heavy imports are lazy; the endpoints work before `requirements-ml.txt`.
