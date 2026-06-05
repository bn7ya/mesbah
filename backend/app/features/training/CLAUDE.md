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

## Gotchas
- Training needs the whole GPU → `launch()` unloads the inference engine first.
- A run with 0 approved examples is marked `failed` early with a helpful message.
- Resuming a parent adapter is handled on the **HF path** (Unsloth path trains a
  fresh adapter); see `scripts/train_qlora.py`.
