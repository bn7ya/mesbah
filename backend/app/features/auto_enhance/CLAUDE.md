# feature: auto_enhance (automated self-improvement loop · التحسين التلقائي)

The model improves itself with no human in the loop: it **asks → answers →
scores its own answer → self-corrects until it passes → curates → trains →
activates the new version → repeats** for N *generations*.

## Files
- `service.py` — pure helpers: `build_ask_messages`, `build_eval_messages`,
  `parse_scores` (robust JSON extraction), `scores_pass`, `create_loop_session`,
  `pick_topic_seed`. Scores are 4 dims (0–10, higher=better):
  `logic, language, context, factuality` (factuality = no hallucination).
- `manager.py` — `AutoEnhanceManager` (`manager`): the daemon-thread orchestrator.
  `start/cancel/is_running/reconcile_orphans`. Emits live events to
  `loops/<id>/events.jsonl`; status lives on the `AutoEnhanceLoop` row.
- `router.py` — REST + the live WebSocket `/api/auto-enhance/loops/{id}/ws`.
- `schemas.py` — `LoopCreate` (defaults pulled from `settings.auto_enhance_*`).

## Loop lifecycle (`pending → running → completed | failed | cancelled`)
Per generation: resolve the **current active version** (so each generation runs on
the version the previous one trained), make a `Session` "تحسين تلقائي · جيل N",
run `turns_per_generation` turns, then train a `TrainingRun` scoped to that
session and **block** until it finishes, then continue.

Per turn (`_run_turn`): ask → answer → evaluate → (correct ↔ re-evaluate up to
`max_correction_rounds`) → **quality gate**. The gate auto-approves the assistant
turn (`set_flags(approved=True)`) **only** when all four scores clear their
thresholds — failing turns stay unapproved so `dataset.collect_examples` skips
them. Provenance in `Message.meta` (`auto_enhance, loop_id, generation, turn,
scores, rounds`).

## VRAM / GPU coordination (important)
- The model stays **resident** across ask/answer/evaluate/correct — reloading the
  same model per phase saves no VRAM (KV-cache is freed after each `generate`).
- The **training** step is the only GPU-exclusive phase: `training_manager.launch`
  calls `inference_engine.freeze()` (unload + refuse loads). `_await_training` does
  **zero generation** while frozen. The training monitor `unfreeze()`s on completion
  **after** it `set_active`s the new version, so `_ensure_loaded_when_ready` waits
  out the brief lingering-freeze race before the next generation loads the new tip.
- **One loop at a time** (single GPU): `start()`/`busy_reason()` refuse if a loop is
  running or `engine.frozen` (a manual training run owns the GPU).

## Event contract (events.jsonl → WS `{"type":"event","data":…}`)
`generation_start · turn_start · ask · answer · evaluation{scores,round} ·
correction{round} · turn_done{approved,scores,rounds} · training_start ·
training_status · training_skipped · generation_done{avg_scores} · loop_done · error`

## Thinking models (Qwen3) — important
The base model is a hybrid-reasoning model that emits `<think>…</think>` before
its answer. Left on, this **breaks the loop**: the evaluator "thinks" instead of
returning JSON (→ all scores parse-fail to 0 → endless useless corrections), and
think blocks pollute the training data. So every loop `generate` call passes
`enable_thinking=False` (threaded into `engine._build_inputs` →
`apply_chat_template`), the evaluator gets a larger token budget, and
`service.strip_think()` defensively removes any residual `<think>…</think>` (and
drops a truncated/unclosed one) from questions, answers, corrections, and before
`parse_scores`. Keep all four — disabling any one reintroduces the zero-score loop.

## Gotchas / known limits
- **Self-training risk:** the model trains on its own self-judged output. The
  quality gate + per-generation isolated sessions + "unparseable eval ⇒ fail"
  mitigate but don't eliminate drift. Keep `generations` low; watch
  `results.generations[].avg_scores` trend.
- The **evaluator is the same model it judges** — biased by construction. Eval runs
  at temperature 0 with a strict numeric rubric; thresholds are user-tunable.
- A loop interrupted by an API restart is marked `failed` (cannot resume — its
  thread is gone). Any in-flight `TrainingRun` is finalized by training's own
  `reconcile_orphans`.
