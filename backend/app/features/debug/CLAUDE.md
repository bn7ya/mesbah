# feature: debug (live status + backend logs)

Read-only diagnostics for the GUI's `/debug` page. **No hard ML imports** —
everything is best-effort so the endpoints answer even without the ML stack,
without a GPU, or mid-failure.

## Files
- `service.py` —
  - `status()` → `{hardware: hardware.snapshot(), gpu_live, engine, downloads,
    active_runs, settings: {selected_gpu_indices, onboarded}, env}`.
  - `gpu_live()` — per-GPU utilization/memory/temperature via **pynvml →
    `nvidia-smi` → `[]`** (same layered-probe pattern as `core/hardware.py`).
  - `RingBufferHandler` + `install_log_buffer()` — a `logging.Handler` keeping
    the last 500 formatted root-logger records in a deque; installed once from
    `main.py`'s lifespan. `recent_logs(n)` returns the tail.
- `router.py` — `GET /api/debug/status`, `GET /api/debug/logs?lines=`.

## Gotchas
- `status()` imports the inference engine / download manager / DB lazily inside
  the function and wraps each source in try/except — one broken subsystem must
  not take the whole snapshot down.
- The log buffer only sees records logged **after** startup (uvicorn's access
  logs propagate to the root logger, so they show up).
