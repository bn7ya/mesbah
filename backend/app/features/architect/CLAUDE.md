# feature: architect (from-scratch model design)

Lets the user **define a new model architecture** (dense or MoE) and see, before
committing, how many parameters it has and whether it can possibly train on the
box. Powers step 2 of the "create model from scratch" wizard.

## Files
- `schemas.py` — `ArchitectureSpec` (family, layers, hidden, heads, vocab,
  context, MoE experts), `FeasibilityEstimate` (`ParamBreakdown` + `MemoryVerdict`
  + warnings).
- `service.py` — pure-Python math: `count_params` (MoE-aware total + active),
  `estimate_memory` (bf16 weights + grads + paged 8-bit optimizer + activations →
  fits / needs_paging / extreme), `estimate`, `solve_hidden` (reverse: hidden_size
  for a target param count), `build_config_dict` (spec → `transformers` config
  kwargs, consumed by `scripts/train_scratch.py`).
- `router.py` — `/api/architect/families|estimate|solve-hidden`.

## Important
- **No torch/transformers import here** — this runs at the API layer, which must
  boot without the ML stack. The spec is only *instantiated* later, in the trainer
  subprocess. Keep `build_config_dict` returning a plain dict.
- Everything is an **estimate** meant to inform/warn, not to be byte-exact.
- Honesty: from-scratch on one 16 GB GPU is compute-bound. `estimate` emits a loud
  warning for ≥1B params or `extreme` memory — the wizard surfaces it. We do not
  hard-cap size (user decision: allow any size, warn loudly).

## Persistence
The chosen spec is saved into `Project.default_train_config["architecture"]` and
the project's `metadata.json`; the trainer reads it back via `build_config_dict`.
