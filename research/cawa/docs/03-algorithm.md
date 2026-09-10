# CAWA · C. Algorithm specification

The normalised architecture graph, the module layout, and complete pseudocode
for the pipeline.

---

## 1. The normalised architecture graph (brief §13)

Parameter names are not the interface. Every model is lifted into a
**circuit-level IR** in which the nodes are gauge-invariant objects
(`01-research-analysis.md` Props. 3–4), not raw tensors.

```
ModelGraph
├── Embed        E ∈ ℝ^{|V|×d}                 tied: bool
├── Block[0..L)
│   ├── read_1   NormSpec(kind=rms|ln, folded=True, eps)
│   ├── Attn     n_q, n_kv, d_h, PosSpec
│   │   └── Head[0..n_q)
│   │       ├── QK   Factored(W_Q ∈ ℝ^{d×d_h}, W_K ∈ ℝ^{d×d_h})     rank ≤ d_h
│   │       ├── OV   Factored(W_V ∈ ℝ^{d×d_h}, W_O ∈ ℝ^{d_h×d})     rank ≤ d_h
│   │       └── kv_group: int                                        GQA provenance
│   ├── read_2   NormSpec
│   └── MLP      m, ActSpec(silu|gelu|relu), gated: bool
│       └── Neuron[0..m)   ν = (g_k ∈ ℝ^d, u_k ∈ ℝ^d, o_k ∈ ℝ^d)
├── FinalNorm    NormSpec
└── Unembed      W_U ∈ ℝ^{d×|V|}
```

Two invariants make the IR useful rather than decorative:

1. **Every node is expressed post-canonicalisation** (`02-math-spec.md` §C1):
   gains folded into readers, centering folded, biases folded, GQA expanded to
   an MHA view, OV in canonical factorisation. Two models in IR form are
   directly comparable; two models in HF form are not.
2. **The IR is a *view*, not a copy.** Nodes hold `torch` views into the live
   state dict where possible, plus the provenance needed to write back
   (`kv_group`, the original `γ`, the GQA repeat factor). Write-back is a
   separate, explicit, reversible operation.

### 1.1 Adapters

```
cawa/architecture/
    base.py           ModelGraph, Block, Head, Neuron, NormSpec, PosSpec, ActSpec
                      canonicalise(graph) -> graph          (C1, exact)
                      writeback(graph, model)               (inverse of the lift)
    llama_adapter.py  Llama / Mistral / Qwen2-3 / TinyLlama / SmolLM  (RMSNorm+SwiGLU+RoPE+GQA)
    gptneox_adapter.py  Pythia / GPT-NeoX  (LayerNorm + GELU + rotary-partial + biases)
```

`gptneox_adapter` exists in v0 **only** so that the Pythia suite is reachable
for the E0 measurements, which need no transfer. Transfer across
`llama ↔ gptneox` is restriction R-3/R-5 and is not attempted in v0.

Adapter contract: `lift(model) -> ModelGraph` and
`writeback(graph, model) -> None` must satisfy
`writeback(lift(m)) ≡ m` functionally, verified by a test asserting
bit-comparable logits (fp32, tolerance `1e-4`) on a fixed batch. **If the
round-trip test fails, no transfer is permitted for that architecture** — an
adapter that cannot reproduce the model it read cannot be trusted to modify it.

---

## 2. Module layout

```
research/cawa/
  cawa/
    architecture/    base.py  llama_adapter.py  gptneox_adapter.py  canonical.py
    analysis/        weight_statistics.py   activation_collector.py
                     cka.py   spectral.py   logit_lens.py
    matching/        layer_matcher.py  head_matcher.py  neuron_matcher.py
                     optimal_transport.py  hungarian.py
    projection/      svd.py  procrustes.py  least_squares.py  embedding_map.py
    transfer/        attention_transfer.py  mlp_transfer.py  norm_transfer.py
                     block_transfer.py  lowrank.py  confidence.py
    evaluation/      perplexity.py  kl.py  representation.py  benchmarks.py
                     acceptance.py
    experiments/     e0_atlas.py  e1_synthetic.py  e2_family.py  e3_pruned.py
                     e4_seeds.py  baseline.py  ablation.py
    tests/
  docs/              (this design)
```

Hard boundaries, enforced by review:

- `architecture/` is the **only** place that knows HF tensor layouts, transpose
  conventions, or module names.
- `matching/`, `projection/`, `transfer/` operate on the IR and on
  `numpy`/`torch` arrays only. They must be testable on synthetic graphs with
  no HF dependency.
- `analysis/` never mutates. `transfer/` never measures. `evaluation/` never
  transfers.

---

## 3. Top-level pipeline

```
function CAWA(S, T, calib, cfg) -> T'

  # ---------- Phase 0: lift, canonicalise, sanity ----------
  G_S ← canonicalise(lift(S));  G_T ← canonicalise(lift(T))
  assert vocab(S) == vocab(T)                                  # R-1, hard gate
  assert roundtrip_logits_ok(G_S, S) and roundtrip_logits_ok(G_T, T)
  A_E, r_E ← embedding_map(E_S, E_T)                           # §2.3 of analysis
  if cfg.assume_A0:  assert ‖E_S − E_T‖ == 0 and A_E == I

  split calib into  FIT / ACCEPT / REPORT   (disjoint documents)

  # ---------- Phase 1: statistics (streaming, one pass each) ----------
  Σ_S ← collect(S, FIT)      # per-layer stream moments, per-head attn patterns,
  evict(S)                   #   per-neuron activation moments, logit-lens dists
  Σ_T ← collect(T, FIT)      # one model resident at a time

  # ---------- Phase 2: depth correspondence ----------
  C   ← layer_cost(Σ_S, Σ_T, E)                                # CKA + logit-lens + reg
  Γ, path ← monotone_dtw(C, band=cfg.band)                     # exact DP
  report alignment_gap = CKA − R²_identity  per pair           # over-reporting check

  # ---------- Phase 3: per-block transfer, in depth order ----------
  T' ← copy(T);  ledger ← []
  for j in 0 .. L_T−1:
      I_j ← { i : Γ[i,j] > 0 }
      if I_j is empty:  continue

      A_diag ← ridge_map(Σ_S[i*], Σ_T[j])                      # diagnostic only
      A      ← procrustes_map(Σ_S[i*], Σ_T[j])                 # conjugation, semi-orth
      ρ      ← retained_energy(A, Σ_S[i*])
      c      ← confidence(Γ, matches, A, ρ, shapes)            # §8 of math spec
      if c < cfg.c_min:  ledger += SKIP(j, "low confidence", c);  continue

      # ---- structural matching (gauge-invariant costs) ----
      π  ← match_heads(G_S.blocks[I_j], G_T'.blocks[j], Σ, A)
      Π  ← match_neurons(G_S.blocks[I_j], G_T'.blocks[j], Σ, A)

      # ---- candidate parameters ----
      cand ← transplant_block(G_S, I_j, Γ, A, π, Π, G_T'.blocks[j])

      # ---- λ by measurement, within the confidence bound ----
      λ* ← golden_section( λ ∈ [0, c^β],
                           objective = NLL(apply(T', j, cand, λ), ACCEPT) )

      Θ_new ← refit_output_maps(T', j, cand, λ*, Σ_T_current)  # ridge (★), error-feedback
      Θ_new ← guardrails(Θ_new, Θ_old)                         # norm / spectral / deviation

      # ---- accept or roll back ----
      if accept(T', j, Θ_new, ACCEPT):                         # paired bootstrap + KL + entropy
           commit(T', j, Θ_new)
           Σ_T ← recollect(T', from_layer=j)                   # error feedback: stream moved
           ledger += ACCEPT(j, I_j, λ*, c, Δnll)
      else:
           rollback(T', j)
           if cfg.enable_lowrank:                              # rung 3 fallback
               ΔW ← lowrank_correction(T', j, target=Y*, r=cfg.rank)
               if accept(T', j, ΔW, ACCEPT):  commit; ledger += ACCEPT_LR(j, ...)
               else: ledger += REJECT(j, reason)
           else: ledger += REJECT(j, reason)

  # ---------- Phase 4: report on untouched data ----------
  metrics ← evaluate(T', T, S, REPORT)      # 4 levels, never substituted (§8 analysis)
  return T', ledger, metrics
```

### 3.1 Sub-procedure: `transplant_block`

```
function transplant_block(G_S, I_j, Γ, A, π, Π, block_T)
  # attention
  for each target head t:
      s* ← argmax_s π[s,t]·importance[s]
      Ŵ_Q[t] ← A† W_Q^S[s*]                 # RoPE-safe: head dims untouched
      Ŵ_K[t] ← A† W_K^S[s*]                 # A† = √(d_S/d_T)(AᵀḠA)⁻¹AᵀḠ
      OV̂[t]  ← Σ_s π[s,t] · A† OV^S[s] A     # merge OV (linear), select QK (nonlinear)
      Ŵ_V[t], Ŵ_O[t], η_t ← truncate_rank(OV̂[t], d_h)
  if target is GQA:
      Ŵ_K^{(g)}, Ŵ_V^{(g)} ← retie_gqa(Ŵ_K, Ŵ_V, Σ)       # Sylvester, §5.6
  # MLP
  Ŵ_g ← A† W_g^S Π ;  Ŵ_u ← A† W_u^S Π ;  Ŵ_d ← Πᵀ W_d^S A
  return candidate parameters + per-component losses (η, ρ, dispersion)
```

Many source blocks → one target block (`|I_j| > 1`): merge in *increment* space,
`Δ̂ = Σ_i Γ[i,j]·Δ_S⁽ⁱ⁾A`, and let the §7 re-fit find the single block that best
reproduces it. Do **not** average the parameters of two source blocks — that
composes nothing (Prop. 5 gives only an approximate justification for merging
functions, none at all for averaging weights across depth).

### 3.2 Sub-procedure: `refit_output_maps` — where the real work happens

```
function refit_output_maps(T', j, cand, λ, Σ)
  # 1. install the input-side (matched, conjugated) parameters
  set W_Q, W_K, W_V, W_g, W_u  from cand at strength λ
  # 2. recollect the block's own pre-output features under the TARGET's real input
  Φ_attn ← stream_accumulate( concat_heads(Attn_j(Ñ(H_T⁽ʲ⁾))) )     ΦᵀΦ, ΦᵀY*
  Φ_mlp  ← stream_accumulate( act(Ñ(H)W_g) ⊙ (Ñ(H)W_u) )
  # 3. desired increment: interpolate in FUNCTION space
  Y*_attn ← (1−λ)·Δ_T,attn + λ·(Δ_S,attn A)
  Y*_mlp  ← (1−λ)·Δ_T,mlp  + λ·(Δ_S,mlp  A)
  # 4. closed-form ridge toward the ORIGINAL target weights   …(★)
  W_O ← (Φ_attnᵀΦ_attn + μI)⁻¹ (Φ_attnᵀ Y*_attn + μ W_O^orig)
  W_d ← (Φ_mlpᵀ Φ_mlp  + μI)⁻¹ (Φ_mlpᵀ  Y*_mlp  + μ W_d^orig)
  return
```

The output-side maps (`W_O`, `W_down`) are *never* copied from the source. They
are always **solved**, because they are the only components whose optimal value
is a convex closed-form function of everything else that was just installed.
This is the mechanism by which the target absorbs discarded heads, merged
neurons, and projection error.

---

## 4. Complexity and cost

Let `d ≈ 2048`, `m ≈ 5504`, `L ≈ 24`, `n_calib ≈ 2·10⁶` tokens.

| Step | Time | Memory |
|---|---|---|
| Statistics, per model | 1 forward pass over calib | `O(L(d² + m²))` fp32 accumulators |
| Layer cost matrix | `O(L² d²)` | `O(d²)` |
| DTW | `O(L²)` | `O(L²)` |
| Head matching | `O(L n² d d_h²)` + `O(n)` ablations | small |
| Neuron matching | `O(L m² d)` for the cost + `O(m³)` Hungarian | `O(m²)` ← dominant |
| Procrustes per pair | `O(d³)` | `O(d²)` |
| Re-fit per block | `O(m² + m d)` accum + `O(m³)` solve | `O(m²)` |
| λ search per block | ~6 forward passes over ACCEPT slice | — |
| Acceptance per block | 1 forward pass over ACCEPT slice | — |

Dominant term is the `O(m²)` neuron cost matrix and the `O(m³)` Hungarian. At
`m = 5504` that is 30 M entries (120 MB fp32) and a ~10 s assignment — fine.
At `m > 16384` switch to Sinkhorn with a sparsified cost (top-k candidates per
neuron from a cheap first-pass screen).

**Whole-pipeline estimate for a 1.5 B-parameter target on one 16 GB card:
2–5 hours**, dominated by the per-block λ search and acceptance forward passes.

---

## 5. Determinism and provenance

Every run emits a `ledger.jsonl`: one record per block with the aligned source
indices, the matching costs and z-scores, `ρ`, `R²`, `c`, `λ*`, the guardrail
values, the accept/reject decision with its p-value, and the NLL delta. A CAWA
model is not a checkpoint, it is a checkpoint **plus its ledger**; a result
without the ledger is not reproducible and is not reportable.

Seeds fixed for: calibration sampling, Sinkhorn initialisation, bootstrap
resampling, and any randomised SVD.

### 5.1 Fit inside Mesbah

CAWA is deliberately isolated under `research/` and wired to neither backend
(see `research/cawa/CLAUDE.md`). If E3/E2 produce a positive result, the natural
product surface already exists: a CAWA run is a **`TrainingRun` that produces a
`ModelVersion`** — a node in Mesbah's version tree with no GPU training step,
branchable and activatable like any other. The ledger is exactly the metrics
payload the version tree already displays. Nothing is built for that until the
research answers the question.
