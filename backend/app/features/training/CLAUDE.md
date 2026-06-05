# feature: training (QLoRA runs)

Builds a dataset from corrected chats, runs a QLoRA fine-tune as a **subprocess**,
streams live metrics, and appends a `ModelVersion` on success.

## Files
- `dataset.py` — `collect_examples` turns every approved assistant turn into an SFT
  example with its preceding context → `{messages:[…]}` JSONL.
- `manager.py` — `TrainingManager` (`manager`): `prepare()` (dataset + config.json),
  `launch()` (unload inference → spawn `scripts/train_qlora.py`), `_monitor()`
  (finalize DB + create version), `cancel()`.
- `router.py` — REST + the **live WebSocket** `/api/training/runs/{id}/ws`.
- (the trainer itself lives at `backend/scripts/train_qlora.py`)

## Subprocess contract
The child reads `runs/<id>/config.json`, appends one JSON point per log step to
`runs/<id>/metrics.jsonl`, and writes terminal `runs/<id>/status.json`
(`{status, adapter_path, metrics, error}`). The WS tails `metrics.jsonl`; the
monitor thread reads `status.json` on exit. **Keep this contract stable** —
both sides depend on it.

## Run lifecycle
`pending → preparing → running → completed | failed | cancelled`.
On `completed`, `_monitor` creates a child `ModelVersion` (via versioning.service),
sets `result_version_id`, and **auto-activates** it.

## Config resolution (precedence)
`project.default_train_config` → `run.config.hyperparams` overrides. `prepare()`
also injects `base_model` (local path preferred), `resume_adapter_path` (parent
adapter, for "enhance from node"), dataset/output/metrics paths, and a
`total_steps` estimate for the progress bar.

## Backends & memory (scripts/train_qlora.py)
- **Unsloth** is preferred for from-base runs (less VRAM, RAM activation offload).
  **HF path** is the fallback: used for resume runs, when Unsloth isn't installed,
  or when Unsloth can't load — and it adds a **VRAM→RAM→disk** offload tier.
- `load_with_offload_fallback`: tier 1 = whole model on GPU (`device_map={"":0}`);
  tier 2 on CUDA OOM = `device_map="auto"` with `max_memory` (GPU cap + `cpu_offload_gb`
  RAM) + `offload_folder` (disk). The manager injects `offload_folder` / `cpu_offload_gb`.
- Dataset is pre-formatted to a `text` column via the chat template (works for both
  trl and Unsloth). `assistant_only_loss` defaults OFF (many templates lack the
  `{% generation %}` mask and would hard-error).

## Gotchas
- Training needs the whole GPU → `launch()` **freezes** the inference engine
  (unload + refuse to load) so a warmup/chat can't steal VRAM mid-run; the monitor
  unfreezes on run end. (Pinning the 4-bit model on GPU avoids bnb's
  "modules dispatched on CPU/disk" error.)
- A run with 0 approved examples is marked `failed` early with a helpful message.
