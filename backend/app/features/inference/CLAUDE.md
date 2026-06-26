# feature: inference (chat generation)

Loads a base model (4-bit) + the active version's LoRA adapter and generates
replies. Used by the sessions feature; also exposed directly for diagnostics.

## Files
- `engine.py` — `InferenceEngine` singleton (`engine`). **All ML imports are lazy.**
- `service.py` — resolves `(model_id, adapter_path, load_in_4bit)` for a (project,
  version) and builds the chat message list. `build_messages`/`stream_reply` for normal chat;
  `build_correction_messages`/`stream_correction` for self-correction (the "magic
  wand") — the correction system prompt **replaces** the session system prompt, the
  draft goes in as the last assistant turn, and a short user trigger asks for the
  rewrite. Used by `sessions` `POST /messages/{id}/self-correct`.
- `router.py` — `/api/inference/status|unload|generate`.

## Engine rules
- **One resident model on 16 GB.** Same base + different version → swap the LoRA
  adapter only; different base → full reload.
  `ensure_loaded(model_id, adapter_path, load_in_4bit=True)`.
- `unload()` frees all VRAM — the **training manager calls it before a run**.
- 4-bit NF4 + bf16 compute for pretrained bases. `status()` reports
  `runtime_available`, loaded model, and live VRAM via `torch.cuda.mem_get_info`.
- Missing torch/transformers → raises `ModelRuntimeUnavailable` → routers turn it
  into a 503 with install guidance.

## Two kinds (resolve_weights is kind-aware)
- **finetune** — `model_id` = the pretrained base (`base_model_local_path`
  preferred over the HF repo so chat never hits the network), loaded **4-bit**; a
  non-base version contributes its LoRA `adapter_path`. Base node → no adapter.
- **scratch** — `base_model_repo` is a synthetic tag (`scratch/qwen3_moe`), NOT a
  real repo. A trained version's `adapter_path` is a **full standalone checkpoint**
  (config + weights + tokenizer), so it loads **directly as the model, no adapter,
  `load_in_4bit=False`** (small bf16 model). An **untrained** scratch project (only
  the base node) has no weights → `resolve_weights` raises `ValueError` → routers
  map it to **409** / SSE error. The workspace blocks chat until trained.

## Gotchas
- A from-scratch model trained on a raw corpus is a **base LM with no chat
  template** → `engine._build_inputs` falls back to plain-text continuation
  (`_plain_prompt`) instead of `apply_chat_template`. Expect text completion, not
  role-based chat.
- Adapter swap falls back to a full reload on any peft hiccup.
- Inference and training contend for the GPU — don't generate during a run.
