# CAWA · E/F/G. Experiments, evaluation, and failure analysis

Experiments are ordered by **cost of being wrong**, not by ambition. Each one
can kill the project cheaply. Predictions are recorded *before* the runs, so a
negative result cannot be re-narrated afterwards.

---

## 0. The falsification target

The core hypothesis, stated so it can fail:

> **H1.** For two language models sharing a vocabulary, there exist depth pairs
> `(i,j)` at which the source's residual-stream content is linearly recoverable
> in the target's stream **beyond what the shared embedding alone explains**,
> and source parameters conjugated by that map improve the target's held-out
> language-modelling loss without any gradient step.

H1 has two separable halves, and they fail differently:

- **H1a (alignment exists).** `ExcessAlign(i,j) = R²(H_S⁽ⁱ⁾→H_T⁽ʲ⁾) − R²(H⁽⁰⁾→H_T⁽ʲ⁾) > 0`
  at useful depths. Falsifiable in **one afternoon**, before any transfer code
  exists.
- **H1b (alignment is usable).** Given H1a, the conjugated parameters actually
  reduce held-out NLL.

H1a can hold while H1b fails — that is the most likely outcome and is a
publishable negative result. H1b cannot hold while H1a fails.

---

## E0 — The mappability atlas (the smallest experiment that can kill CAWA)

**This is the answer to brief §25.9, and it must be run first.** No transfer,
no matching, no weight modification. Three sub-experiments, all of which are
second-order statistics over forward passes.

### E0-a · The embedding anchor (five minutes, no GPU, no calibration data)

For every candidate pair sharing a tokenizer, solve the ridge
`A_E = (E_SᵀE_S + μI)⁻¹E_SᵀE_T` and report `R²`, the CCA spectrum, and
`‖A_E‖₂/‖A_E‖_F` (how close to orthogonal).

*Why it matters.* Under A2 (`d_S ≠ d_T`) `A_E` is the only data-free anchor
that exists. Its `R²` upper-bounds the plausibility of everything downstream.

**Prediction P-a:** `R²(A_E) ∈ [0.6, 0.9]` for same-family different-size pairs
(shared training data ⇒ shared semantic geometry), and `< 0.4` across families.
The CCA spectrum will show a long tail rather than a clean `d_T`-dimensional
shared subspace.

### E0-b · Stream mappability vs depth (the decisive plot)

For each depth pair `(i,j)`, on 2 M tokens of calibration text (mixed English
+ **Arabic long-context**, matching Mesbah's actual domain), report:

```
R²_identity(i,j)      (only meaningful under A0/A1)
R²_procrustes(i,j)    (semi-orthogonal — the map transfer can actually use)
R²_ridge(i,j)         (unconstrained — the ceiling for linear methods)
CKA(i,j)
ExcessAlign(i,j)      ← the number that decides H1a
ρ(i,j)                (retained energy — the P2 bottleneck)
erank(Cov(H_S⁽ⁱ⁾))    (the same bottleneck, source side only)
```

**Prediction P-b1:** `R²_ridge` will be high (>0.9) at `i=j=0` and decay with
depth. **Prediction P-b2:** `ExcessAlign` will be *near zero at shallow depth*
— the apparent early agreement is the shared embedding still dominating the
sum `H⁽ˡ⁾ = H⁽⁰⁾ + ΣΔ`, not shared computation. This is the trap the control
exists to catch. **Prediction P-b3:** `ExcessAlign` peaks somewhere in the
middle third and is small (`< 0.2`) everywhere for independently trained pairs.
**Prediction P-b4:** `R²_procrustes ≪ R²_ridge` — the constraint that RMSNorm
requires (Prop. 7) costs real fit, and the gap is the hidden tax on every
transplant.

### E0-c · The oracle stitch (upper bound on all linear transfer)

Splice: run `T` up to layer `j`, apply a closed-form ridge map, continue with
`S`'s layers from `i` onward, and measure NLL. This changes the architecture and
is therefore **not a deliverable** — it is the ceiling.

**Prediction P-c:** the oracle stitch will be substantially worse than either
model alone at most `(i,j)`. If the oracle is bad, rungs 1–3 of the fallback
ladder cannot be good, and we learn it before writing `transfer/`.

### Kill criterion K0

> If `max_{i,j} ExcessAlign(i,j) < 0.10` **and** the oracle stitch never comes
> within 20 % NLL of `min(NLL_S, NLL_T)`, then **H1a is false for that pair**
> and no transfer method built on linear stream maps can work on it. Record it,
> and move to a pair where it is not false — or, if it is false for every pair,
> report that as the project's finding.

---

## E1 — Synthetic recovery (does the machinery do what it claims?)

Ground truth is known by construction. These are **correctness tests, not
evidence about LLMs**, and must never be cited as such.

| # | Construction | Must recover |
|---|---|---|
| E1-a | `T := S` with a random neuron permutation `P` | `Π = P` exactly; NLL identical |
| E1-b | `T := S` with a random per-head `R ∈ GL(d_h)` on `(W_V, W_O)` | function unchanged; head matching still perfect (proves Prop. 3 handling) |
| E1-c | `T := S` with a random `Q ∈ O(d)` on the stream **and `E`** | Procrustes recovers `Q` to `<1e−4`; transferred model matches bit-for-bit |
| E1-d | `T := S` projected to `d_T < d_S` by a known semi-orthogonal `A` | `ρ` matches the analytic retained energy; recovered `A` ≈ true `A` up to sign |
| E1-e | Two-layer source collapsed into one by construction | DTW finds the 2→1 alignment |
| E1-f | **Shuffled-source null** | ~0 blocks accepted |

E1-b is the sharpest test of the central theoretical claim: a naive
`αQ+βK+γV+δO` head score **must fail** this test while the circuit score
passes. Include the naive scorer in the test suite specifically so this failure
is demonstrated and regression-tested, not merely asserted.

---

## E2 — Same family, different size (assumption A2)

Candidate pairs — availability to be verified before use:

- **Pythia** 160M → 410M → 1.4B (shared tokenizer, shared training data and
  data order; different `d`, `L`, `n_heads`). The cleanest scientific control
  in open LLMs, and the reason `gptneox_adapter` exists.
- **SmolLM2** 135M / 360M / 1.7B.
- **Qwen3** 0.6B / 1.7B / 4B (RMSNorm + SwiGLU + GQA — matches the v0 adapter,
  and matches the base model family Mesbah already targets).

Direction matters: transfer **large → small** (the source has capability the
target lacks — P5's precondition) and report small → large as a control that
should *not* help.

---

## E3 — Structured-pruning recovery (the headline testbed, assumption A0 exactly)

Construct `T` from `S` by structured pruning that **preserves `d` and `E`**:
drop layers, drop MLP neurons by importance, drop KV-head groups. Then `S` and
`T` genuinely differ in `L`, `m`, `n_kv` — the v0 supported difference set
(R-8) — while satisfying `E_S = E_T` **exactly**, which is the only way the
brief's mandatory assumption and its heterogeneity requirement can both hold
(see `01-research-analysis.md` §2.3).

This testbed has everything the others lack:

- a **known** correspondence (ground truth for the matcher),
- a **large, known** capability gap (`NLL_T ≫ NLL_S`), so P5's precondition
  holds by construction,
- a **real task with real baselines**: training-free recovery of a pruned LLM,
  compared against SparseGPT-style layer-wise reconstruction and against
  LoRA recovery (gradient-based, as the upper reference we are not allowed to
  use but must report).

**Prediction P-3:** CAWA recovers a meaningful fraction of the pruning loss
here — this is the single most likely positive result in the project — and the
credit will be attributable mostly to the closed-form re-fit (`02` §7) rather
than to the structural matching. The ablations are designed to detect exactly
that, and if true it is an honest and interesting finding: *the alignment
machinery matters less than the regression*.

---

## E4 — Different seeds, same architecture (negative control)

`pythia-160m-seed1` vs `pythia-160m-seed2`: identical architecture, identical
data, different initialisation. This is the Git Re-Basin setting.

**Prediction P-4: this will fail**, and it should. Permutation alignment does
not linearly connect two independently trained transformer LMs. If CAWA reports
success here, the reporting is broken — check the metric before celebrating.
E4 exists to catch a broken evaluation harness, which is a more likely source
of a positive result than a genuine one.

---

## E5 — Cross-family, shared tokenizer (the hard case)

Deferred until E2/E3 resolve. Requires lifting R-3/R-5.

---

## Baselines (brief §15)

Every result table carries all of these, on the REPORT split:

| # | Baseline | Applicable when |
|---|---|---|
| 1 | Original target `T` | always — the number to beat |
| 2 | Source `S` | always — context, not a competitor (different arch) |
| 3 | Naive layer-`N`-to-layer-`N` weight interpolation | only when shapes match |
| 4 | Model soup / SLERP / TIES / DARE | only when shapes match; **baselines, not CAWA** |
| 5 | SparseGPT-style layer-wise reconstruction toward `S`'s outputs | always — the closest honest competitor |
| 6 | CAWA weight-only (no activations) | always |
| 7 | CAWA activation-guided | always |
| 8 | CAWA-LR (rung 3) | always |
| 9 | LoRA recovery, gradient-trained | E3 only — the reference ceiling we may not use |

Baseline 5 matters most: if closed-form reconstruction toward the source
achieves the same result *without any of CAWA's matching machinery*, then the
matching machinery is not the contribution and the paper is about something
else. Preregistering this comparison is what stops the project from claiming
credit for its most elaborate component by default.

---

## Metrics — four levels, never substituted

Per `01-research-analysis.md` §8:

```
parameter:      ‖W_T' − W_T‖_F/‖W_T‖_F, ‖W_T' − Ŵ_S‖, spectral distances
representation: CKA, ExcessAlign, stream R², per-layer ‖Δ‖ profile
functional:     KL(T'‖T), top-1 agreement, logit correlation, attention entropy
task:           held-out NLL / perplexity (en + ar), ARC-e, HellaSwag, MMLU-subset
systems:        params, VRAM, tokens/s (must be unchanged — shapes are preserved)
```

**Only the `task` row can support a claim of success.** A run in which
representation similarity rises and held-out NLL also rises is filed as a
failure *and* as evidence that representation similarity is a misleading proxy.

Arabic evaluation is not decoration: Mesbah's target domain is Arabic
long-context, capabilities are known to be unevenly distributed across
languages, and a transfer that helps English while damaging Arabic would be
invisible to an English-only harness.

---

## Ablations (brief §16)

Each toggles one factor; all report the same four-level metric block.

| Group | Arms |
|---|---|
| Matching | none (identity) · weight-only cost · activation-only · combined |
| Neuron alignment | off · Hungarian · Sinkhorn/OT |
| Head alignment | off · circuit cost · **naive Q/K/V/O cost** (expected to fail, kept as evidence) |
| Depth alignment | layer-`N`-to-`N` · unconstrained Hungarian · monotone DTW |
| Layer metric | CKA · logit-lens JS · regression `R²` · combined |
| Projection | identity · truncated SVD · Procrustes · whitened Procrustes · unconstrained ridge |
| λ | fixed grid {0.1,…,0.9} · confidence formula `c^β` · held-out search |
| Re-fit | off (pure parameter interpolation) · **on (★)** |
| Error feedback | off (fit all blocks against the original stream) · on (recollect) |
| Scope | attention-only · MLP-only · both · CAWA-LR only |
| Granularity | layer · head · neuron |

The two arms whose outcomes would most change the design: **re-fit off/on**
(does Prop. 8's correction matter in practice?) and **error feedback off/on**
(does sequential recollection matter at LLM depth?). Both are predicted to
matter a great deal, and both are cheap to test.

---

## Failure analysis protocol (brief §22-G)

When a block is rejected, the ledger already records *what* failed. The
protocol says how to find out *why*, and it is part of the deliverable rather
than an afterthought:

1. **Localise.** Attention-only and MLP-only arms isolate the sub-block.
2. **Decompose the error.** For the rejected block, report the increment error
   `‖Δ_T' − Y*‖/‖Y*‖` split into: projection loss (`1−ρ`), rank-truncation loss
   (`η`), matching residual, and re-fit residual. These sum to the total; the
   largest term names the culprit.
3. **Check the bottleneck.** If `erank(Cov(H_S)) ≫ d_T`, the failure is the P2
   information bound, not the algorithm — no code change fixes it.
4. **Check monotonicity.** If the unconstrained assignment beats the DTW path
   by more than the preregistered margin, the monotonicity assumption is wrong
   for this pair and should be reported as such.
5. **Check the null.** Compare against the shuffled-source run. If the real run
   and the null run behave alike, the pipeline is measuring noise.

Negative results are written up in `docs/07-results.md` with the same care as
positive ones. "CAWA does not work on pair X, and here is the term in the error
decomposition that dominates" is a genuine contribution; a project that only
reports its successes has not measured anything.
