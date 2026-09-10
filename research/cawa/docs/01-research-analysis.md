# CAWA · A. Research analysis

*What is theoretically feasible, what is not, and which assumptions are load-bearing.*

Read this before the math spec. Every design decision in `02-math-spec.md`
and `03-algorithm.md` traces back to one of the propositions here.

---

## 0. Notation and conventions

Row-vector convention throughout: activations are `X ∈ ℝ^{n×d}` (n tokens,
d channels) and weights act on the right, `X W`, with `W ∈ ℝ^{d_in×d_out}`.

> **Implementation note.** HuggingFace `nn.Linear` stores `weight ∈ ℝ^{d_out×d_in}`
> and computes `X Wᵀ`. Every `W` in these documents is the *transpose* of the
> stored tensor. `cawa/architecture/` is the only place allowed to know this;
> everything above it sees the row convention.

A decoder-only transformer `M = (E, {B^(ℓ)}_{ℓ<L}, N_f, W_U)`:

```
H⁽⁰⁾ = E[x]                                              E ∈ ℝ^{|V|×d}
H⁽ˡ⁺¹⁾ = H⁽ˡ⁾ + Attn⁽ˡ⁾(N₁⁽ˡ⁾(H⁽ˡ⁾))  + MLP⁽ˡ⁾(N₂⁽ˡ⁾(·))
Z      = N_f(H⁽ᴸ⁾) W_U                                   W_U ∈ ℝ^{d×|V|}
```

We write `Δ⁽ˡ⁾ = H⁽ˡ⁺¹⁾ − H⁽ˡ⁾` for the **residual-stream increment** written by
block ℓ. Blocks *read* the stream through a norm and *write* increments back;
this read/write framing is the one CAWA operates in.

RMSNorm: `Ñ(h) = h / √(‖h‖²/d + ε)`, and `N(h) = Ñ(h) ⊙ γ` with a learned gain.

Subscripts `S` / `T` denote source and target. `d_S, L_S, n_S` etc.

---

## 1. The gauge group of a transformer

Any statement of the form "source weight `W_S` resembles target weight `W_T`"
is only meaningful if both are expressed in a common coordinate system. The
first job is to find out how much coordinate freedom actually exists. **The
answer is not what the model-merging literature assumes**, and it drives
almost everything else.

### C1 — Canonicalisation (exact, functional no-ops)

Before anything is compared, both models are pushed into a canonical form by
transformations that provably do not change the function computed:

| Op | Transformation | Exact? |
|----|---------------|--------|
| **Gain folding** | `N(h) W = Ñ(h) · diag(γ) W`; set `γ ← 1` | yes |
| **Centering folding** (LayerNorm) | mean subtraction `= h C`, `C = I − 11ᵀ/d`; fold `C` into readers | yes |
| **Bias folding** | absorb reader biases into the block's write path where the path is linear | yes for O / down |
| **GQA expansion** | materialise per-query-head `W_K, W_V` by repeating the group's tensors | yes (view) |
| **OV factorisation** | replace `(W_V, W_O)` by `OV = W_V W_O` and re-factor canonically | yes |

After C1 both models are "gainless-RMSNorm, no stream biases, MHA-view"
models. This is what makes Propositions 1–4 apply verbatim.

### Proposition 1 — the residual stream is defined only up to O(d)

*For a canonicalised RMSNorm transformer, let `Q ∈ O(d)`. The parameter map*

```
E ← E Q,   W_read ← Qᵀ W_read,   W_write ← W_write Q,   W_U ← Qᵀ W_U
```

*leaves the logits exactly unchanged.*

**Proof.** `‖hQ‖ = ‖h‖`, so `Ñ(hQ) = Ñ(h)Q`. A reader sees
`Ñ(hQ)·QᵀW = Ñ(h)W` — unchanged. Its output is therefore unchanged, and a
writer emits `(…)·W_write Q`, which lands in the rotated stream consistently.
By induction `H⁽ˡ⁾ ← H⁽ˡ⁾Q` for all ℓ, and `N_f(H⁽ᴸ⁾Q)·QᵀW_U = N_f(H⁽ᴸ⁾)W_U`. ∎

RoPE is untouched because it acts *inside* head coordinates, after the read
projection. For LayerNorm models the group shrinks to the stabiliser of `1`,
`{Q ∈ O(d) : Q1ᵀ = 1ᵀ} ≅ O(d−1)`.

> This is the same invariance SliceGPT and QuaRot/SpinQuant exploit. Its
> consequence for CAWA is blunt: **raw weight comparison between two
> independently trained models is meaningless.** `‖W_S − W_T‖` and
> `cos(W_S, W_T)` are not functions of the models' behaviour. Any similarity
> score built from them is measuring gauge, not function.

### Proposition 2 — an identical embedding matrix destroys that freedom

*If `E_S = E_T = E` and `rank(E) = d`, the only gauge element relating the two
stream bases is `Q = I`.*

**Proof.** `E Q = E ⟹ E(Q − I) = 0`. `E` has full column rank (|V| ≫ d, and
for every real LM the embedding matrix is full rank), so `Q = I`. ∎

**This is the single most important consequence of the mandatory assumption,
and it is the opposite of what the assumption is usually assumed to buy.**
The shared embedding does not *help us find* a hidden rotation between the
models. It proves **there is no hidden rotation to find**. The two models are
already co-registered at ℓ = 0.

Two corollaries follow immediately.

**Corollary 2.1 (double anchoring).** If additionally the LM heads are tied
(`W_U = Eᵀ`), the stream basis is pinned at *both* ends of the network. Both
models must read tokens from, and write logits into, literally the same
directions of `ℝ^d`.

**Corollary 2.2 (misalignment is real).** Under Prop. 2, any observed
mismatch between `H_S⁽ⁱ⁾` and `H_T⁽ʲ⁾` for i, j > 0 is **genuine functional
divergence, not a coordinate artifact**. There is no transformation that
repairs it without cost. Every alignment map CAWA estimates for i, j > 0 is
a lossy approximation, and its residual is a real error budget — not a
numerical nuisance to be tuned away.

### Proposition 3 — attention has a GL(d_h) gauge; Q/K/V/O are individually meaningless

*Per head h, the block's function depends on `(W_Q, W_K, W_V, W_O)` only through*

```
QK⁽ʰ⁾ = W_Q⁽ʰ⁾ (W_K⁽ʰ⁾)ᵀ ∈ ℝ^{d×d}     (rank ≤ d_h)
OV⁽ʰ⁾ = W_V⁽ʰ⁾  W_O⁽ʰ⁾    ∈ ℝ^{d×d}     (rank ≤ d_h)
```

*modulo the RoPE caveat below. Additionally, heads may be permuted freely.*

**Proof (OV).** For any `R ∈ GL(d_h)`, `(W_V R)(R⁻¹ W_O) = W_V W_O`. The head's
contribution `Aₕ · Ñ(H) W_V W_O` is unchanged. **(QK, no RoPE).** Logits are
`Ñ(hᵢ) W_Q W_Kᵀ Ñ(hⱼ)ᵀ`; only the product enters. **(heads).** Head outputs are
summed into the stream, so permuting heads together with their `W_O` blocks is
exact. ∎

**RoPE caveat.** With RoPE the attention logit is
`Ñ(hᵢ) W_Q R_{m−n} W_Kᵀ Ñ(hⱼ)ᵀ` for every relative offset `m−n`. Replacing
`(W_Q, W_K) ← (W_Q A, W_K B)` preserves all of them iff `A R_Δ Bᵀ = R_Δ ∀Δ`.
The orthogonal solutions are `A = B` in the commutant of `{R_Δ}`, i.e.
block-diagonal with 2×2 rotation blocks: the torus `∏_j SO(2)`, dimension
`d_h/2`, plus permutations of frequency-identical pairs (none, since RoPE
frequencies are distinct). **So RoPE collapses the QK gauge from GL(d_h) to a
`d_h/2`-torus.** The OV gauge stays full GL(d_h) — RoPE never touches the V path.

> **This invalidates the head-similarity score proposed in the brief**
> (`Score = αQ + βK + γV + δO`). `W_V` and `W_O` are individually pure gauge:
> two heads computing the *identical* function can have `W_V` matrices with
> cosine similarity 0. Comparing them measures nothing. CAWA compares `QK` and
> `OV` circuits, computed in factored form (see §2 of the math spec).

### Proposition 4 — the MLP neuron gauge, and what a neuron actually *is*

SwiGLU neuron k contributes `x ↦ σ(x·g_k)(x·u_k) o_k` where `g_k, u_k ∈ ℝ^d`
are rows of gate/up and `o_k ∈ ℝ^d` is a row of down.

*The gauge group is `P_m ⋉ (ℝ*)^m`: permutation of neurons, and reciprocal
scaling `(u_k, o_k) ← (c u_k, o_k/c)`. The gate row `g_k` admits **no** scaling
freedom because SiLU is not homogeneous.*

Hence the gauge-invariant descriptor of a SwiGLU neuron is

```
ν_k = ( g_k ,  u_k o_kᵀ )        — a direction and a rank-1 read→write map
```

For a gated-free MLP (GELU/`down∘φ∘up`) the gauge is permutation only and
`ν_k = (u_k, o_k)` jointly. For ReLU MLPs positive scaling `(u,o) ← (cu, o/c)`
*and* `(u_k, o_k) ← (c u_k, o_k/c)` with `c>0` is free (ReLU is positively
homogeneous), so `ν_k = (û_k, ‖u_k‖ o_k)` with `û` unit.

**Consequence.** Neuron matching must score `g` by direction and the read/write
pair by the rank-1 outer product — *not* by concatenating raw `[g; u; o]`
vectors, which is scale-gauge-dependent.

### Proposition 5 — depth has no exact gauge, only an approximate one

There is no exact transformation relating an L-layer model to an L′-layer one.
But in the small-increment regime (`‖Δ⁽ˡ⁾‖ ≪ ‖H⁽ˡ⁾‖`, empirically true in the
middle of large LMs) the residual stack behaves like a discretised flow, and
two layers of half strength approximate one layer. This is the *only*
justification for many-to-one depth matching, and it is an approximation whose
error grows with increment magnitude — which is exactly where transfer matters
most (early and late layers have the largest relative increments). Document
this as an assumption, measure `‖Δ⁽ˡ⁾‖/‖H⁽ˡ⁾‖` per layer, and distrust
many-to-one merges where that ratio is large.

### Summary of the gauge picture

| Object | Exact freedom | What is invariant |
|---|---|---|
| Residual stream | `O(d)` — **but `I` only, under Prop. 2** | everything, once E is shared |
| Attention head index | permutation | multiset of heads |
| QK (no RoPE) | `GL(d_h)` | `W_Q W_Kᵀ` |
| QK (RoPE) | torus `∏ SO(2)`, dim `d_h/2` | `{W_Q R_Δ W_Kᵀ}_Δ` ≈ the pair itself |
| OV | `GL(d_h)` | `W_V W_O` |
| MLP neurons | `P_m ⋉ (ℝ*)^m` | `(g_k, u_k o_kᵀ)` |
| Depth | none | — |

---

## 2. What the shared embedding buys — and what it does not

The brief calls `E_S = E_T` the "primary global semantic anchor". It is an
anchor, but a much more specific one than the framing suggests.

### 2.1 It gives

1. **Gauge elimination** (Prop. 2). No rotation search. This removes the single
   hardest optimisation problem in the merging literature.
2. **A shared, exact, data-free interpretive basis.** Because both models write
   logits through the same `E`, any residual vector in either model can be read
   out as a token distribution — the *logit lens*:
   ```
   p⁽ˡ⁾ = softmax( Ñ(H⁽ˡ⁾) · diag(γ_f) Eᵀ / τ )
   ```
   Comparing `p_S⁽ⁱ⁾` to `p_T⁽ʲ⁾` by JS divergence is a **functional**
   depth-similarity metric, expressed in units that mean something (next-token
   belief), and it exists *only* because the vocabulary and unembedding are
   shared. This is CAWA's best layer-correspondence signal and, as far as we
   can tell, is not used for cross-model alignment anywhere in the literature.
3. **A closed-form cross-width map when `d_S ≠ d_T`** (see 2.3).
4. **A common input distribution.** `H_S⁽⁰⁾ = H_T⁽⁰⁾` exactly, for any token
   sequence. Layer 0 alignment is free and perfect.

### 2.2 It does *not* give

- Any claim about layers ℓ > 0. Corollary 2.2.
- Any information about head or neuron indices — those gauges are internal and
  survive Prop. 2 untouched.
- Anything about positional encoding, context length, or attention structure.
- **Comparability of weights.** `W_Q^S` vs `W_Q^T` is still meaningless
  (Prop. 3). Shared `E` fixes the *stream* basis, not the *head-internal* basis.

### 2.3 The assumption is self-contradictory as stated — and here is the fix

The brief requires `E_S = E_T` (§2) **and** support for different hidden
dimensions (§3). These are mutually exclusive: `E ∈ ℝ^{|V|×d}`, so `d_S ≠ d_T`
forces `E_S ≠ E_T`. The two requirements cannot both hold.

**Resolution — the anchor that actually generalises is the shared *vocabulary*,
not the shared matrix.** With one tokenizer, `E_S` and `E_T` are two
`|V|×d` matrices whose **rows are paired**. That is a supervised regression
problem with `|V| ≈ 10⁵` paired examples and `d ≈ 10³` unknowns per column —
massively overdetermined, and solvable in closed form with no calibration data
at all:

```
A_E = argmin_A ‖E_S A − E_T‖²_F + μ‖A‖²_F  =  (E_Sᵀ E_S + μI)⁻¹ E_Sᵀ E_T
```

The residual `1 − R²(A_E)` is a *free, exact, five-second measurement* of how
much of the target's embedding geometry is linearly reachable from the source's.
Its CCA spectrum counts the shared semantic directions. **This is the first
experiment we should run** (E0-a), because it upper-bounds the plausibility of
everything downstream in the `d_S ≠ d_T` regime.

So the assumption ladder becomes:

| Level | Assumption | Anchor strength |
|---|---|---|
| **A0** | `E_S = E_T` (same matrix) | gauge fully pinned, `A_E = I` exactly |
| **A1** | same tokenizer, `d_S = d_T`, different `E` | rows paired; `A_E` estimable, near-orthogonal expected |
| **A2** | same tokenizer, `d_S ≠ d_T` | rows paired; `A_E` is a genuine projection, lossy |
| **A3** | different tokenizers | requires token-level OT / shared-string matching — **out of scope for CAWA v0** |

A0 is the strict reading of the brief and is only realisable **by
construction** (see §5): no two off-the-shelf models with different
architectures share an embedding matrix. That is not a reason to drop it —
it is a reason to *build* the A0 testbed, because A0 is the regime where the
theory is cleanest and the hypothesis is most sharply falsifiable.

---

## 3. The five hardest theoretical problems

### P1 — The residual streams are not in a common basis beyond layer 0

Prop. 2 pins ℓ = 0 and (with tied heads) the output. Everything between is
free to diverge, and does. The stream at depth ℓ is
`H⁽ˡ⁾ = H⁽⁰⁾ + Σ_{k<ℓ} Δ⁽ᵏ⁾`, and the two models' `Δ` sequences are unrelated.

**The trap this creates.** Because `H⁽⁰⁾` is *literally identical* between the
models, any similarity metric applied to `H_S⁽ⁱ⁾` vs `H_T⁽ʲ⁾` will report high
similarity at shallow depth **for a reason that has nothing to do with
transferable structure** — the shared embedding is simply still the dominant
term in the sum. A naive `R²`-vs-depth curve will look encouraging and mean
nothing.

**Mandatory control — excess alignment.** Every representation-similarity
number reported in CAWA must be quoted against the embedding-only null model:

```
ExcessAlign(i,j) = R²( H_S⁽ⁱ⁾ → H_T⁽ʲ⁾ )  −  R²( H⁽⁰⁾ → H_T⁽ʲ⁾ )
```

Only `ExcessAlign > 0` is evidence of shared computation. This control is
cheap, and without it the project is capable of producing a confident,
completely spurious positive result. It is the concrete form of the brief's
§17 warning.

### P2 — The dimensional bottleneck is an information bound, not an engineering problem

**Lemma (bottleneck).** For any stream map `A ∈ ℝ^{d_S×d_T}` with `d_T < d_S`,
transferring via `Ŵ = A⁺ W_S A` makes the transplanted component blind to a
subspace of dimension ≥ `d_S − d_T`: `A⁺A` is a rank-`d_T` projector. The
retained fraction of the source's input energy is at best

```
ρ = Σ_{k≤d_T} σ_k²  /  Σ_k σ_k²        σ_k = singular values of Cov(Ñ(H_S⁽ⁱ⁾))
```

So **cross-width transfer fidelity is capped by the effective rank of the
source's residual stream**, which is a property of the source alone and is
measurable in one pass, before any transfer code is written. If
`erank(Cov(H_S)) ≫ d_T`, the ceiling is low and no amount of clever matching
raises it. (Empirically LLM residual covariance spectra are heavy-tailed but
*not* low-rank; expect this to bite.)

### P3 — RMSNorm does not commute with non-conformal maps

The conjugation `Ŵ = A⁺ W_S A` silently assumes `Ñ(xA) ∝ Ñ(x)A`. Gainless
RMSNorm is `Ñ_d(x) = x·√d/‖x‖`, and the two sides live in different dimensions,
so the exact relation is

```
Ñ_{d_T}(xA)  =  √(d_T/d_S) · κ(x) · Ñ_{d_S}(x) A ,        κ(x) = ‖x‖/‖xA‖
```

The constant `√(d_T/d_S)` is harmless — it is absorbed into the conjugated
weights. `κ(x)` is not: it is a **per-token** rescaling.

**Proposition 7.** `κ(x) ≡ const` for all `x` **iff** `AAᵀ = c²I_{d_S}`, i.e.
`A` has orthogonal *rows*.

**Proof.** `‖xA‖² = x A Aᵀ xᵀ`; this equals `c²‖x‖²` for all `x` iff
`AAᵀ = c²I_{d_S}`. ∎

This gives an asymmetry that is easy to miss and matters a great deal:

- **Widening (`d_T ≥ d_S`) is norm-safe.** `A` can have orthonormal rows, `κ ≡ 1`,
  and the commutation is *exact*. Nothing is lost.
- **Narrowing (`d_T < d_S`) is not.** `AAᵀ` has rank `d_T < d_S` and can never
  be `c²I_{d_S}`, so *no* choice of `A` commutes. The best available choice is
  orthonormal *columns* (`AᵀA = I_{d_T}`), for which `‖xA‖ = ‖P_A x‖` with
  `P_A = AAᵀ` the rank-`d_T` projector, so `κ(x) = ‖x‖/‖P_A x‖ ≥ 1` and

  ```
  ρ  =  tr(P_A Ḡ_SS) / tr(Ḡ_SS)  =  Σ_x ‖P_A x‖² / Σ_x ‖x‖²  =  E_w[ κ(x)⁻² ],   w(x) ∝ ‖x‖²
  ```

  That is, **`ρ` is the energy-weighted mean of the per-token retained
  fraction `κ⁻²`** — exactly, by construction. (The *unweighted* mean of `κ⁻²`
  is a different number: a ratio of expectations is not an expectation of a
  ratio. They are close in practice — 0.6540 vs 0.6516 on a synthetic stream
  with `cond(Ḡ) ≈ 9·10⁵` — but only the weighted form is an identity.)

  **The projection loss and the RMSNorm non-commutation error are therefore the
  same quantity `ρ`** — they do not
  compound into two separate error budgets, which is the one piece of good news
  in this proposition.

**Design consequence, and it is counter-intuitive.** An unconstrained ridge map
maximises `R²` but introduces a *second, uncounted* error when used to
conjugate weights, because it distorts norms and RMSNorm is sensitive to that.
**Prefer semi-orthogonal (Procrustes / principal-subspace) maps for weight
conjugation even at the cost of a worse `R²`,** and reserve unconstrained ridge
for cases where the map only defines a *regression target in activation space*
(where no commutation is needed). This splits CAWA's projection module into two
different tools for two different jobs — see math spec §4.

**A second consequence.** Even with a semi-orthogonal `A`, the naive
conjugation `Ŵ = AᵀW_S` is only the least-squares solution when the stream
covariance is isotropic. The correct **activation-weighted conjugation** is

```
Ŵ = (Aᵀ Ḡ A)⁻¹ Aᵀ Ḡ W_S ,      Ḡ = Ñ(H_S)ᵀ Ñ(H_S)
```

On a synthetic stream with `cond(Ḡ) ≈ 1.6·10⁵` — the right order for an LLM
residual stream with massive-activation channels — this reduces the conjugation
residual by **76 %** against plain `AᵀW_S`. The same theme recurs in Prop. 8:
*whenever a formula ignores the activation covariance, it is the isotropic
special case of a better one.*

### P4 — Attention patterns cannot be merged; only OV circuits can

When `n_S > n_T` the brief proposes head merging by clustering / OT /
weighted aggregation. This is valid for **OV** (linear: the average of two
rank-`d_h` circuits is a well-defined `d×d` matrix, re-truncatable by SVD) and
**invalid for QK**. The attention pattern is `softmax(QKᵀ/√d_h)`; averaging two
`QK` circuits does *not* produce a head whose pattern is the average of the two
patterns — softmax is not affine, and the average of an induction head and a
previous-token head is neither.

**Therefore: merge OV, select QK.** When the target has fewer heads, choose
which source heads survive by measured importance (ablation effect on
calibration NLL), and blend only their OV circuits into the survivors. This is
a substantive correction to the brief's §7.

### P5 — Alignment quality and functional benefit are different axes

Even a perfect alignment does not imply `T' > T`. Transfer moves `T` toward
`Π_arch(T)(S)` — the best representation of `S`'s function inside `T`'s
architecture. This helps **only if** (a) `S` has capability `T` lacks, (b) that
capability is localised in components CAWA can move, and (c) the projection
loss is smaller than the capability gap. For two well-trained models of similar
quality, (c) will almost certainly fail — the projection loss is large and the
gap is small.

**This dictates experiment design**: pick pairs where the gap is large and
known. See §5.

---

## 4. Can the alignment map be propagated through depth? (brief §9)

The brief asks whether `A_0 = I` can be propagated forward to give `A_i`. The
answer is **no, and it is also unnecessary.**

*No*: the blocks are nonlinear, so a conjugation relation
`A_{i+1} ≈ J_T⁻¹ A_i J_S` holds only to first order, and residual blocks are
non-contractive (`f(x) = x + g(x)` has Lipschitz constant ≥ 1 in the directions
that matter). Error therefore compounds at least additively and generally
multiplicatively:

```
‖ε_{i+1}‖ ≤ Lip(f_T)·‖ε_i‖ + r_i ,   Lip(f_T) ≳ 1
```

There is no contraction to save us. Ten layers of propagation from an
`r_i ≈ 0.1` local residual is a destroyed map.

*Unnecessary*: re-estimating `A_ij` from data at each depth costs one streaming
accumulation of `X_SᵀX_S` (`d²` floats) and `X_SᵀX_T` (`d_S d_T` floats) plus
one Cholesky — negligible, and never worse than propagation. **CAWA
re-anchors at every depth from calibration statistics and never propagates.**

The one genuinely useful thing that survives from the propagation idea is
diagnostic: measuring how fast `A_ii` drifts away from `I` (under A0) is a
direct measurement of how quickly the two models stop sharing a basis, i.e. of
the shape of the P1 curve.

---

## 5. Where the idea cannot work — stated up front

These are predictions, made before the experiments, so that a negative result
cannot be quietly re-narrated as a success.

1. **Two independently trained LLMs of comparable quality.** Transfer will not
   improve either. Prop. 2 + P5. Expect NLL to degrade monotonically with λ.
   This is the regime the brief's framing implicitly hopes for, and it is the
   least likely to work.
2. **Different-seed, same-architecture merge (the Git Re-Basin setting).**
   Permutation alignment alone does not put two independently trained
   transformer LMs on a linear-mode-connected path. Published attempts largely
   fail for transformers at LM scale. We include it as a **negative control**
   and *predict failure*; if CAWA "succeeds" here without a functional
   improvement metric, the metric is broken, not the model.
3. **Cross-tokenizer transfer** (A3). Out of scope; the anchor does not exist.
4. **MoE models.** Routing makes "neuron k" a conditional object; the neuron
   gauge in Prop. 4 does not apply. Out of scope for v0.
5. **Arbitrary architectures** (CNN ↔ transformer etc.). There is no shared
   stream, no shared basis, no shared read/write structure. The only surviving
   idea is behavioural (input/output) matching, which is distillation, which
   needs gradients. Effectively infeasible without training.

And the two regimes where it is genuinely plausible:

6. **Structured-pruning recovery.** `T` obtained from `S` by removing layers /
   MLP neurons / KV heads keeps `d` and `E` *identical* (assumption A0 exactly),
   has a large, known capability gap, and has ground-truth correspondence. This
   is the natural headline testbed, and "training-free recovery of a pruned
   model" is a real, publishable task with real baselines.
7. **Same-family, different-size** (Pythia 160m→410m, SmolLM2, Qwen3 sizes).
   Shared tokenizer, shared training data, genuinely different `d`, `L`, heads.
   Assumption A2. Harder, more interesting, more honest.

---

## 6. Answering the brief's central question (§14): what should CAWA operate on?

The brief offers: (A) raw weights, (B) activations, (C) component-group
functions, (D) residual-stream transformations, (E) subspace geometry, (F) a
combination. Our answer, in priority order:

> **D ≻ C ≻ B ≻ E ≻ A.**
> CAWA should be a **residual-stream method that manipulates gauge-invariant
> circuits, using activations to define the objective, and writes to weights
> only as the final step.**

Reasoning:

- **(A) raw weights — reject as the primary object.** Prop. 1 and Prop. 3 make
  raw weights gauge-dependent. Any algorithm whose decisions are functions of
  raw weight statistics (Frobenius cosine, mean/std, row distributions — all
  suggested in the brief §4) is making decisions on the basis of coordinates,
  not behaviour. Weight statistics survive only as *cheap screening* and as
  gauge-*invariant* summaries (singular-value spectrum, effective rank,
  spectral entropy are all `O(d)`-invariant and therefore legitimate).
- **(B) activations — necessary but not sufficient.** They are the only
  observable and must define the objective, but they do not tell you which
  parameters to change.
- **(C) circuits** (`QK`, `OV`, neuron `(g, uoᵀ)`) — the correct *parameter*
  objects: they are exactly the gauge-invariant content of the weights.
- **(D) the residual stream** — the only *shared coordinate system* the two
  models possess (Prop. 2), and the space in which block outputs compose
  additively. Alignment, confidence and rollback all live here.
- **(E) subspace geometry** — the right tool for the `d_S ≠ d_T` map (P2, P3),
  subordinate to D.

### 6.1 The strongest reformulation: closed-form functional re-fit

The deepest change we propose to the brief is to the *transfer* step itself.

The brief's equation `W_T' = (1−λ)W_T + λ·P_out Π W_S P_in` maps *parameters*
and hopes the function follows. The stronger, still gradient-free, formulation
maps the **function** and solves for the parameters:

```
given   the target block's real input activations under the current model,
        and a desired residual-stream increment Y*,
solve   the block's output-side linear map in closed form
        W* = argmin_W ‖Φ W − Y*‖²_F + μ‖W − W_T‖²_F
```

This is exactly the layer-wise reconstruction primitive that makes
GPTQ / SparseGPT / AWQ work — a family of methods that demonstrably modify LLM
weights substantially with closed-form least squares and **no gradients at
all**. It is the strongest precedent that this class of method can work at
scale, and CAWA should be built on it rather than on parameter interpolation.

Two results make this more than a preference:

- **Prop. 8 (in the math spec):** the brief's interpolation equation is the
  *isotropic special case* of this ridge, recovered exactly when `ΦᵀΦ ∝ I`.
  Real activation covariances are catastrophically anisotropic (LLM residual
  streams have a handful of "massive activation" channels with 10²–10³× the
  typical norm), so the isotropic case never holds and the interpolation
  equation is provably the wrong estimator.
- The ridge form gives confidence *for free*: `μ` is the shrinkage, and the
  achieved residual is the confidence.

### 6.2 The fallback ladder

If full block transplantation fails — which §5 predicts for most pairs — the
core objective ("transfer useful behaviour without gradients") survives at
lower rungs. Ordered by decreasing structural ambition and increasing
robustness:

| Rung | Method | Shape change | Risk |
|---|---|---|---|
| 1 | full block transplant | none | very high |
| 2 | circuit-level transplant (selected heads / neurons) | none | high |
| 3 | **CAWA-LR: closed-form low-rank correction** `W ← W + UVᵀ`, `U,V` from ridge | none | low |
| 4 | closed-form *stitch* (`T` layers ⊕ linear map ⊕ `S` layers) | changes arch — **diagnostic only** | n/a |

Rung 3 deserves emphasis: it produces a LoRA-*shaped* delta computed by least
squares rather than by gradient descent, which satisfies "no LoRA training"
literally and in spirit, never changes shapes, and has a bounded, controllable
deviation from `T`. It is the most likely thing in this project to actually
produce `T' > T`.

Rung 4 is not a deliverable — it changes the architecture — but it is the
**oracle**: a closed-form ridge stitch measures the best any linear-map-based
transfer could possibly do. If the oracle stitch is bad, rungs 1–3 are dead,
and we learn that in an afternoon instead of a month.

---

## 7. What is closed-form / non-gradient solvable

| Sub-problem | Method | Closed form? |
|---|---|---|
| Layer correspondence | DP over a cost matrix (monotone DTW) | exact, `O(L_S L_T)` |
| Head correspondence (balanced) | Hungarian on circuit distances | exact, `O(n³)` |
| Head correspondence (unbalanced) | entropic / unbalanced OT (Sinkhorn) | iterative but convex |
| Neuron correspondence | Hungarian or Sinkhorn on `ν_k` costs | as above |
| Stream map, unconstrained | ridge normal equations + Cholesky | exact |
| Stream map, orthogonal | Procrustes = SVD of `X_SᵀX_T` | exact |
| Stream map, subspace | CCA (generalised eigenproblem) / truncated SVD | exact |
| Output-weight re-fit | ridge with `ΦᵀΦ` accumulated streaming | exact |
| Low-rank correction | truncated SVD of the ridge residual | exact |
| Confidence | regression residuals + permutation test | exact |
| λ selection | 1-D search on held-out NLL (forward passes only) | not closed form, but gradient-free |
| Accept / rollback | paired significance test on held-out NLL | gradient-free |

**Not** closed-form: the *joint* problem (matching × projection × weights) is a
nonconvex assignment problem. CAWA solves it by **alternating exact steps**
(Procrustes ↔ Hungarian, an EM-style block-coordinate descent). Each step is
closed-form and non-increasing in the objective, so the alternation is
monotone and terminates — with no gradients anywhere.

---

## 8. Distinguishing the four kinds of "it worked"

Per the brief's §17, CAWA reports four *separate* families of metric and never
substitutes one for another:

| Level | Metric | What a gain proves |
|---|---|---|
| **Parameter similarity** | `‖W_T' − Ŵ_S‖`, cosine | *nothing* — gauge-dependent (Prop. 1, 3) |
| **Representation similarity** | CKA, `ExcessAlign`, stream `R²` | the alignment step behaved; **not** that the model is better |
| **Functional similarity** | KL(`T'`‖`T`), top-1 agreement, logit corr | how much was changed, not whether it helped |
| **Task performance** | held-out NLL / perplexity, benchmark acc | the only thing that counts |

**Rule.** No claim of success is made from anything above the last row. A rise
in representation similarity accompanied by a rise in held-out NLL is recorded
as a *failure*, and specifically as evidence that representation similarity is
a misleading proxy — which is itself a finding worth reporting.
