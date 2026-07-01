# feature: debug (frontend)

`DebugPage` (route `/debug`, wrench icon in the topbar) — live diagnostics.

- Polls `api.debugStatus()` + `api.debugLogs(200)` every **3 s** (interval cleared
  in `ngOnDestroy`).
- Sections: environment chips (Python/torch/transformers/ML-stack, RAM, selected
  VRAM), per-GPU utilization + memory bars (+ temperature, "مُختارة" tag from
  `hardware.selected_gpus`), inference-engine state, downloads table, active
  training runs (router links to the project workspace), and an LTR dark log box
  (same styling as the training panel's terminal).
- All labels Arabic, technical terms English (per the app convention).
