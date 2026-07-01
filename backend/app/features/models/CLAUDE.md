# feature: models (HuggingFace registry)

Discover and download base models — listed **live from the HF API**, no
hardcoded catalog.

## Files
- `router.py` — `/api/models/featured|search|local|download|download/status|downloads`,
  plus `datasets/search`, `datasets/preview`, `inspect`, and `hf-token` (GET/POST/DELETE).
- `service.py` — live featured listing (`list_featured`), HF model+dataset search,
  local registry, background downloads, `inspect_model` (reads a repo's
  `config.json`), `dataset_preview` (columns via the datasets-server HTTP API),
  and HF-token persistence.

## HuggingFace token (GUI-settable)
- `GET /hf-token` → `{configured, source: env|file|null, hint}` (never the secret).
- `POST /hf-token {token}` → validates via `whoami` (400 if invalid), persists to
  `data/hf_token` (chmod 600), applies to `settings.hf_token` + `HF_TOKEN`/
  `HUGGING_FACE_HUB_TOKEN` env so search/download authenticate immediately.
- `DELETE /hf-token` → removes the file, reverts to the env value.
- `apply_persisted_token()` runs at import so the first request is authenticated.
  A UI-set file token takes precedence over `MISBAH_HF_TOKEN`. **Search still uses
  the new `huggingface_hub` 1.x API — `sort="downloads"`, no `direction` arg.**

## New discovery endpoints
- `GET /datasets/search?query=` — HF dataset search (the training-corpus picker).
- `GET /datasets/preview?repo_id=` — column/text-field listing for a dataset.
- `GET /inspect?repo_id=` — architecture facts from `config.json` (hidden_size,
  vocab_size, MoE block, context). Used to validate a pretrained **embedding
  source** for from-scratch projects. Gated/private/missing → clean 403/404/502.
  Still **no torch**: only the small config file is fetched, never a model.

## Behaviours
- `list_featured(limit, language)` — `GET /featured` — lists the most-downloaded
  `text-generation` models live via `HfApi.list_models(pipeline_tag=…,
  filter=language, sort="downloads")` (`language=ar` powers the Arabic section;
  hub 1.x dropped the `language=` kwarg, language codes are plain tags). Hits are
  normalized to `{repo_id, label, downloads, likes, tags, license, params, gated,
  source:"hub"}` (`params` best-effort from the repo name). Results are cached
  in-process for ~15 min; on any hub error the endpoint degrades to `list_local()`
  mapped to the same shape with `source:"local"` — it never 500s. Precise facts
  (context length, model_type) come lazily from `GET /inspect` on selection.
  `docs/MODEL_SELECTION.md` remains as *guidance* only.
- `search` uses `huggingface_hub.HfApi.list_models`; falls back to filtering the
  local registry when the hub is unreachable (offline-friendly).
- `DownloadManager` runs `snapshot_download` on a background thread; `status()`
  reports **bytes-on-disk** so the GUI can animate a progress bar. A 14B model is
  ~28 GB → downloads are long; status survives restarts by scanning the dir.
  `list_all()` / `GET /downloads` reports every download tracked this session —
  drives the global topbar chip and the debug page.

## Gotchas
- Local models live in `data/models/<repo__with__double__underscore>`; the path
  encoding (`/` → `__`) is shared between `start` and `status`.
- All heavy imports are lazy; the endpoints work before `requirements-ml.txt`.
- **httpx/brotli download crash:** huggingface_hub 1.x downloads via httpx, whose
  brotli decoder raises mid-stream (`DecodingError: brotli … can_accept_more_data()
  is False`). `core/hf_http.py::disable_httpx_brotli()` (called in `main.py`
  lifespan; the trainers register the same factory in their `main()`) makes the
  client advertise only `gzip, deflate` so the Hub never serves brotli. Don't
  re-enable brotli. `HF_HUB_ENABLE_HF_TRANSFER` is **dead** in hub 1.x (warns only).
