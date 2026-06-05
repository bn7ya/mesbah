# feature: inference (chat generation)

Loads a base model (4-bit) + the active version's LoRA adapter and generates
replies. Used by the sessions feature; also exposed directly for diagnostics.

## Files
- `engine.py` — `InferenceEngine` singleton (`engine`). **All ML imports are lazy.**
- `service.py` — resolves `(base_id, adapter_path)` for a (project, version) and
  builds the chat message list.
- `router.py` — `/api/inference/status|unload|generate`.

## Engine rules
- **One resident model on 16 GB.** Same base + different version → swap the LoRA
  adapter only; different base → full reload. `ensure_loaded(base_id, adapter_path)`.
- `unload()` frees all VRAM — the **training manager calls it before a run**.
- 4-bit NF4 + bf16 compute + `device_map="auto"`. `status()` reports
  `runtime_available`, loaded model, and live VRAM via `torch.cuda.mem_get_info`.
- Missing torch/transformers → raises `ModelRuntimeUnavailable` → routers turn it
  into a 503 with install guidance.

## Gotchas
- `resolve_weights` prefers `project.base_model_local_path` over the HF repo so
  chat never hits the network. Base node → no adapter.
- Adapter swap falls back to a full reload on any peft hiccup.
- Inference and training contend for the GPU — don't generate during a run.
