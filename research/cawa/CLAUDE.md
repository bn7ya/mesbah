# research/cawa — CAWA (Cross-Architecture Weight Adaptation)

Research prototype for gradient-free cross-architecture parameter transfer
between LLMs. **Isolated from both of Mesbah's backends**: it is not imported
by `backend/app/` (the live FastAPI product) nor by `backend/apps/` (the Django
migration target), and it has no API surface, no models and no frontend. Do not
wire it to either backend.

## Current state

**Design only — no pipeline code.** `docs/00-summary.md` … `docs/06-feasibility.md`
are the complete technical design (research analysis, math spec, algorithm spec,
experiment plan, related work, feasibility gates). `README.md` indexes them.

`verify_design_claims.py` numerically checks every load-bearing proposition
(numpy only, seconds to run). **Run it after editing any equation in `docs/`,
and add a check for any proposition you add.** It currently verifies 18 claims;
if a doc change makes it fail, the doc is wrong until proven otherwise — two
errors in the first draft were caught this way.

## Rules for working here

- **Read `docs/01-research-analysis.md` before changing any equation.** Every
  design decision in `02` and `03` traces to a proposition there; the
  propositions about gauge invariance (1–4) and the RMSNorm/least-squares
  results (7–8) are load-bearing and several of them contradict the obvious
  approach.
- **Nothing skips the gates in `docs/06-feasibility.md` §5.** Implement E0
  first. G3 (synthetic recovery) and G4 (null run) are non-negotiable before
  any result is reported.
- **Never claim success from parameter, representation or functional
  similarity.** Only held-out task loss on the REPORT split counts
  (`01` §8). A run where representation similarity rises and NLL also rises is
  filed as a failure.
- **Keep architecture-specific code in `cawa/architecture/`.** Nothing else may
  know HF tensor layouts or transpose conventions. Research logic is tested on
  synthetic graphs with no `transformers` dependency.
- **Every run emits `ledger.jsonl`.** A CAWA model is a checkpoint *plus* its
  ledger; a result without one is not reportable.
- This directory is English-only — it is research code and documentation, not
  product surface. Mesbah's Arabic-UI rule does not apply here. Arabic *does*
  appear as calibration and evaluation data (`docs/04-experiments.md`), because
  the product's target domain is Arabic long-context.

## Update this file when

The state line changes (design → E0 implemented → gates passed), the module
boundaries in `docs/03-algorithm.md` §2 change, or a gate outcome is recorded.
