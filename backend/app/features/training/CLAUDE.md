# feature: training (QLoRA runs)

Builds a dataset from corrected chats, runs a QLoRA fine-tune as a **subprocess**,
streams live metrics, and appends a `ModelVersion` on success.

## Files
- `dataset.py` — `collect_examples` turns every approved assistant turn into an SFT
  example with its preceding context → `{messages:[…]}` JSONL.
- `manager.py` — `TrainingManager` (`manager`): `prepare()` (dataset + config.json),
  `launch()` (unload inference → spawn the trainer), `_monitor()` (finalize DB +
  create version), `cancel()`.
- `router.py` — REST + the **live WebSocket** `/api/training/runs/{id}/ws`.
- trainers: `scripts/train_qlora.py` (finetune) and `scripts/train_scratch.py`
  (from-scratch full training). `launch()` picks by `cfg["kind"]`.

## Two kinds (by `project.kind`)
- **finetune** — `prepare()` builds the dataset from approved chat turns (as
  before), now written under `projects/<pid>/data/`; QLoRA via `train_qlora.py`.
- **scratch** — no chat dataset; the config carries an `architecture` spec, an
  `embedding_mode` (`new`/`pretrained`, always trainable), a **`datasets`** corpus
  list, and offload knobs. `train_scratch.py` builds the model from config (random
  init), ingests the corpora, and full-trains. Checkpoints land in
  `projects/<pid>/versions/<run_id>/`.
  - **Multiple datasets:** `default_train_config["datasets"]` is a list of
    `{repo, config, split, text_field, max_samples?}`. `load_corpus` loads +
    tokenizes each (per-dataset `max_samples` cap), `concatenate_datasets`,
    shuffles (seed), then applies the global `max_train_samples` cap. The legacy
    single `dataset_repo`/`text_field` fields still work (fallback in
    `_dataset_specs`) and are mirrored from the first entry by the UI.

## ZeRO-Infinity (scratch + paged_training)
To train a model larger than 16 GB **to completion**, the scratch trainer uses
**DeepSpeed ZeRO-3 / ZeRO-Infinity**: params+grads+optimizer offload to host RAM
then NVMe (`deepspeed_config.build_ds_config`; `offload_target` auto/cpu/nvme,
`est_host_ram_gb` + `nvme_path` injected by `prepare()`). The trainer builds
`HfDeepSpeedConfig` before the model (ZeRO-3 partitions at init), passes
`deepspeed=ds_config.json` to the HF `Trainer`, and `launch()` sets the
single-process distributed env (`RANK/WORLD_SIZE/MASTER_*`). Falls back to
single-GPU placement (with a warning) if DeepSpeed isn't installed. Slow but
finishes — it does not fix the compute/data need (see docs/HARDWARE.md).

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
