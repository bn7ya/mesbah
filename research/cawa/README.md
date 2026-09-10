# CAWA — Cross-Architecture Weight Adaptation

Research prototype: transfer useful parameters from a source LLM `S` into a
target LLM `T` **without any gradient descent, optimiser, backpropagation,
fine-tuning, LoRA training or distillation** — using only closed-form linear
algebra, combinatorial assignment, and forward passes over calibration data.

```
T' = Adapt(S, T, D_calib)        Arch(T') = Arch(T)
```

**Status: design only.** No implementation yet. The design is deliberately
complete before any code is written, because the cheapest experiment (E0) can
falsify the core hypothesis in an afternoon and would make most of the
implementation pointless.

CAWA is **not** model merging. Soups, SLERP, TIES, DARE and task arithmetic all
require a common parameter space; CAWA's problem starts where that assumption
fails. They appear here only as baselines.

---

## Read in this order

| Doc | Contents |
|---|---|
| [`docs/00-summary.md`](docs/00-summary.md) | the twelve answers, with pointers — **start here** |
| [`docs/01-research-analysis.md`](docs/01-research-analysis.md) | the gauge group of a transformer, what the shared embedding really buys, the five hardest problems, where the idea cannot work |
| [`docs/02-math-spec.md`](docs/02-math-spec.md) | every equation with its derivation, assumptions and failure mode |
| [`docs/03-algorithm.md`](docs/03-algorithm.md) | the normalised architecture graph, module layout, full pseudocode |
| [`docs/04-experiments.md`](docs/04-experiments.md) | E0–E5, baselines, ablations, preregistered predictions, failure protocol |
| [`docs/05-related-work.md`](docs/05-related-work.md) | the five neighbourhoods and precisely how CAWA differs |
| [`docs/06-feasibility.md`](docs/06-feasibility.md) | feasibility scores, decision gates, honest summary |
| [`verify_design_claims.py`](verify_design_claims.py) | numerical proof of every load-bearing claim above — `numpy` only, runs in seconds |

```
$ python research/cawa/verify_design_claims.py
...
18/18 claims verified
```

A design document that asserts propositions should be able to prove them. The
script caught two real errors during drafting: `ρ` is the *energy-weighted*
mean of the per-token retained fraction, not the plain mean (a ratio of
expectations is not an expectation of a ratio), and the naive conjugation
`Ŵ = AᵀW_S` needed replacing with its activation-weighted form.

---

## The four results that shape everything else

**1 · The shared embedding eliminates the gauge rather than revealing it.**
If `E_S = E_T` with full column rank, the only residual-stream rotation
relating the two models is the identity. There is no hidden alignment to
search for — and therefore every mismatch at depth > 0 is *real functional
divergence*, not a coordinate artifact.

**2 · Raw `W_Q/W_K/W_V/W_O` comparisons measure gauge, not function.**
`(W_V R, R⁻¹ W_O)` computes the same thing for any invertible `R`. Head
matching must use the `QK` and `OV` circuits. RoPE independently collapses the
QK gauge to a `d_h/2`-torus.

**3 · Parameter interpolation is the isotropic special case of a data-aware
ridge.** `W' = (1−λ)W_T + λŴ_S` is exactly `(ΦᵀΦ+μI)⁻¹(ΦᵀY* + μW_T)` when
`ΦᵀΦ ∝ I`. LLM activation covariances are extremely anisotropic, so CAWA
*solves* for output-side weights instead of interpolating them — the same
closed-form primitive that makes GPTQ/SparseGPT work without gradients.

**4 · The obvious positive result is a trap.** Because `H⁽⁰⁾` is literally
identical between the models, similarity metrics report high early agreement
for reasons that have nothing to do with transferable structure. Every number
is quoted as **excess** over the embedding-only null, and every run is checked
against a **shuffled-source null**.

---

## Feasibility, before any experiment

| Class | Score /100 |
|---|---:|
| Same architecture, different sizes | 45 |
| Closely related architectures | 25 |
| Substantially different transformer architectures | 8 |
| Arbitrary neural architectures | 2 |
| Structured-pruning recovery (`d`, `E` preserved) | **70** |
| The E0 measurement being worth publishing regardless of outcome | 90 |

The ambitious form — transplanting between two independently trained,
comparable-quality LLMs — is unlikely to work, for mathematical rather than
engineering reasons. The design says so up front, and the experiments are
built to detect that rather than to obscure it.

---

## Next step

Implement **E0 only** (`docs/04-experiments.md` §E0): the embedding-anchor
regression, the stream-mappability atlas with the `ExcessAlign` control, and
the closed-form oracle stitch. Gate on **G1** before anything in `transfer/`
is written.
