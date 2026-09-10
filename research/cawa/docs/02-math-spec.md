# CAWA · B. Mathematical specification

Every equation CAWA implements, with its derivation, its assumptions, and its
failure mode. Conventions as in `01-research-analysis.md` §0 (row vectors,
`X W`, `W ∈ ℝ^{d_in×d_out}`).

Symbols used throughout:

```
A_ij ∈ ℝ^{d_S×d_T}   stream map, source depth i → target depth j
Π    ∈ ℝ^{m_S×m_T}   neuron assignment / transport plan (rows sum ≤ 1)
π    ∈ ℝ^{n_S×n_T}   head assignment / transport plan
λ    ∈ [0,1]         transfer intensity
c    ∈ [0,1]         confidence
Ñ(·)                 gainless RMSNorm
```

---

## 1. Calibration statistics — everything streams

**Requirement (brief §20): never hold the calibration activations in memory.**
Every quantity CAWA needs is a second-order statistic, accumulated in one pass
per model in `O(d²)` memory, `fp32` accumulators (`fp64` on CPU for the solves).

For each recorded site (a layer's stream, a block's pre-output features) keep:

```
n    ← n + n_b
s_X  ← s_X + Σ_b x                      ∈ ℝ^{d}
G_XX ← G_XX + Σ_b xᵀx                   ∈ ℝ^{d×d}
G_XY ← G_XY + Σ_b xᵀy                   ∈ ℝ^{d_S×d_T}   (cross-model, same token order)
```

Centered versions follow algebraically: `Ḡ_XY = G_XY − s_Xᵀ s_Y / n`.

**Linear CKA from these alone** (Kornblith et al., feature-space form):

```
CKA(X,Y) = ‖Ḡ_XY‖²_F / ( ‖Ḡ_XX‖_F · ‖Ḡ_YY‖_F )
```

so CKA, ridge, Procrustes, CCA and the reconstruction residuals are *all*
computable without ever materialising an `n×d` activation matrix. This is the
single design decision that makes CAWA runnable on one 16 GB card.

Cross-model statistics require **token-aligned** forward passes: identical
tokenizer, identical batches, identical order. Guaranteed by assumption A0/A1/A2.

**Outlier channels.** LLM residual streams contain a handful of "massive
activation" channels with 10²–10³× the typical magnitude. Untreated, they
dominate every Frobenius-norm objective. Define `D_X = diag(√(diag(Ḡ_XX)/n))`
and work in standardised coordinates `X̃ = X D_X⁻¹`; recover the map by
`A = D_S⁻¹ Ã D_T`. Always report `κ(Ḡ_XX) = σ_max/σ_min` alongside any solve.

---

## 2. Gauge-invariant descriptors

### 2.1 Attention head h

```
QK⁽ʰ⁾ = W_Q⁽ʰ⁾ (W_K⁽ʰ⁾)ᵀ        OV⁽ʰ⁾ = W_V⁽ʰ⁾ W_O⁽ʰ⁾        both d×d, rank ≤ d_h
```

Never materialised. All required quantities are computed in factored form at
`O(d·d_h²)`:

```
⟨OV_s, OV_t⟩_F = tr( (W_V^sᵀ W_V^t) (W_O^t W_O^sᵀ) )
‖OV_s‖²_F      = tr( (W_V^sᵀ W_V^s) (W_O^s W_O^sᵀ) )
```

and identically for `QK` with `(W_Q, W_K)` in place of `(W_V, W_O)`.

**Canonical OV factorisation** (fixes the `GL(d_h)` gauge, Prop. 3). Thin SVD
of the factored product: compute `QR` of `W_V = Q_V R_V` and `W_Oᵀ = Q_O R_O`,
SVD the small `R_V R_Oᵀ = U Σ Vᵀ`, then

```
W_V^can = Q_V U Σ^{1/2}       W_O^can = Σ^{1/2} Vᵀ Q_Oᵀ
```

Unique up to sign per singular direction (and up to rotation within any
degenerate singular subspace). Cost `O(d d_h² )`.

### 2.2 MLP neuron k (Prop. 4)

```
SwiGLU:  ν_k = ( ĝ_k ,  u_k o_kᵀ )      canonicalise ‖u_k‖ = 1, scale into o_k
GELU:    ν_k = ( û_k ,  ‖u_k‖ o_k )     no gate; scaling gauge absent, so keep magnitudes
```

Plus the activation statistics of neuron k over calibration, streamed:
`(E[a_k], E[a_k²], E[a_k a_l])` for the correlation term. `E[a a]` is `m×m`;
for `m ≈ 10⁴` that is 400 MB in fp32 — accumulate in fp32 on CPU, or subsample
neurons when `m > 8192`.

---

## 3. Layer correspondence

### 3.1 Cost matrix

Three signals, each normalised to `[0,1]`:

```
C^cka[i,j]  = 1 − CKA( H_S⁽ⁱ⁾ , H_T⁽ʲ⁾ )                     rotation-invariant, coarse
C^lens[i,j] = JS( p_S⁽ⁱ⁾ ‖ p_T⁽ʲ⁾ ) / log 2                   functional, needs shared E
C^reg[i,j]  = 1 − R²( H_S⁽ⁱ⁾ A → H_T⁽ʲ⁾ )                     what actually bounds transfer
```

with the logit lens `p⁽ˡ⁾ = softmax( Ñ(H⁽ˡ⁾) diag(γ_f) Eᵀ / τ )`, `τ = 1`.

```
C = w_c·C^cka + w_l·C^lens + w_r·C^reg + ρ_d · (i/L_S − j/L_T)²
```

`w` chosen by ablation E1-c; the depth prior `ρ_d` keeps the alignment near the
diagonal in relative depth.

> **Metric selection is itself a research result, and the brief's preference
> for CKA is questioned.** Under Prop. 2 the gauge is already fixed, so CKA's
> rotation invariance *discards usable information*: it cannot distinguish "the
> streams agree" from "the streams agree up to a rotation that no transplant
> can realise". `C^reg` measures the quantity that actually appears in the
> transfer error bound. Report the **alignment gap** `CKA − R²_identity`
> per layer pair; a large gap is a warning that CKA is over-reporting.

### 3.2 Monotone alignment by dynamic programming

Alignment must be monotone in depth (brief §4). Solve with DTW step set
`{(1,1), (1,0), (0,1)}`:

```
D[i,j] = C[i,j] + min( D[i−1,j−1], D[i−1,j] + β_h, D[i,j−1] + β_v )
D[0,0] = C[0,0]
```

`β_h, β_v > 0` penalise many-to-one steps. Backtracking from `D[L_S−1, L_T−1]`
yields a monotone path; converting the path to a row-normalised plan
`Γ ∈ ℝ^{L_S×L_T}`, `Γ[i,j] = 1/|{i′ : (i′,j) ∈ path}|`, gives the weights for
many-to-one merges. `O(L_S L_T)` time, exact.

Band constraint `|i/L_S − j/L_T| ≤ w` (default `w = 0.25`) prevents the
pathological orderings named in the brief and cuts cost further.

**Non-monotone escape hatch.** If the unconstrained Hungarian assignment on `C`
beats the DP path by more than a preregistered margin, record it as evidence
against the monotonicity assumption rather than silently overriding it.

---

## 4. Stream maps — two different tools for two different jobs

Prop. 7 forces a split that a single least-squares module would get wrong.

### 4.1 Diagnostic map (unconstrained, maximal `R²`)

Used **only** to measure alignment and to define regression targets in
activation space — never to conjugate weights.

```
A_ls = ( Ḡ_SS + μI )⁻¹ Ḡ_ST          μ = α · tr(Ḡ_SS)/d_S ,  α ∈ [1e−3, 1e−1]
R²   = 1 − ‖X_S A − X_T‖²_F / ‖X_T − X̄_T‖²_F
     = 1 − ( tr Ḡ_TT − 2 tr(Aᵀ Ḡ_ST) + tr(Aᵀ Ḡ_SS A) ) / tr Ḡ_TT
```

— note the residual is computable from the accumulators alone. Solve by
**Cholesky of `Ḡ_SS + μI`**, never `pinv`; on Cholesky failure raise `α` by 10×
and retry (the SparseGPT damping loop). `α` selected by generalised
cross-validation over a log grid.

### 4.2 Conjugation map (semi-orthogonal, RMSNorm-safe)

Used whenever the map will be pushed *into* weights.

Reduced-rank orthogonal Procrustes: with the thin SVD `Ḡ_ST = U Σ Vᵀ`,

```
A_proc = U_{:,:r} V_{:,:r}ᵀ  ∈ ℝ^{d_S×d_T} ,   r = min(d_S, d_T)
```

the exact maximiser of `tr(Aᵀ Ḡ_ST)` subject to semi-orthogonality (Schönemann).

**The narrow/wide asymmetry (Prop. 7).** Which semi-orthogonality you get is
decided by the shapes, and the two cases are not equally benign:

| case | property | RMSNorm commutation |
|---|---|---|
| **widening** `d_T ≥ d_S` | `A Aᵀ = I_{d_S}` (orthonormal rows) | **exact**, `κ ≡ 1`, `ρ = 1` |
| **narrowing** `d_T < d_S` | `AᵀA = I_{d_T}` (orthonormal cols) | approximate, `κ(x) ≥ 1` |

so `d_S → d_T` *up* is free and *down* is not. Both carry the harmless global
constant `√(d_T/d_S)`, which is absorbed into the conjugated weights.

**Retained energy.** For the narrowing case, with `P_A = A Aᵀ` the induced
rank-`d_T` projector on `ℝ^{d_S}`:

```
ρ = tr( P_A Ḡ_SS ) / tr( Ḡ_SS ) = E_w[ κ(x)⁻² ] ∈ (0,1] ,      w(x) ∝ ‖x‖²
```

`ρ` is the **energy-weighted** mean of the per-token retained fraction `κ⁻²`;
the unweighted mean is a different (nearby) number, since a ratio of
expectations is not an expectation of a ratio. Only the weighted form is an
identity, and it is the one the accumulators give for free.

By Prop. 7 `ρ` is *simultaneously* the projection loss and the RMSNorm
non-commutation error. `ρ` is therefore the single scalar that bounds cross-width
transfer fidelity (the P2 bottleneck lemma), and it feeds directly into the
confidence in §8.

**Whitened variant.** When channel scales are extreme, solve Procrustes in
CCA-whitened coordinates:
`A = Ḡ_SS^{−1/2} · Procrustes(Ḡ_SS^{−1/2} Ḡ_ST Ḡ_TT^{−1/2}) · Ḡ_TT^{1/2}`,
then re-orthogonalise by polar decomposition. Higher `R²`, weaker Prop. 7
guarantee — report both and let E1-e decide.

**Under A0 (`E_S = E_T`, `d_S = d_T`) the identity is always a candidate.**
Always evaluate `A = I` alongside the estimated map: if `R²(I) ≈ R²(A_proc)`,
no projection is needed and one whole source of error disappears.

---

## 5. Head correspondence and transfer

### 5.1 Cost

```
C^h[s,t] =  α·d_QK(s,t) + β·d_OV(s,t) + γ·d_attn(s,t)
d_QK = 1 − ⟨QK_s, QK_t⟩_F / (‖QK_s‖_F ‖QK_t‖_F)         (factored, §2.1)
d_OV = 1 − ⟨OV_s, OV_t⟩_F / (‖OV_s‖_F ‖OV_t‖_F)
d_attn = mean over calibration positions of JS( A_s(·|q) ‖ A_t(·|q) )
```

`d_attn` — the divergence between the actual attention distributions — is
expected to dominate (E1-d tests this); it is the only term that is directly
behavioural. `α, β` operate on gauge-invariant circuits per Prop. 3; **no term
uses `W_Q, W_K, W_V, W_O` individually.**

### 5.2 Assignment

- `n_S = n_T`: Hungarian on `C^h`, `O(n³)`, exact.
- `n_S ≠ n_T`: entropic unbalanced OT,
  `π = argmin ⟨π, C^h⟩ − ε H(π)` with marginals `(a, b)`, `a_s ∝` head importance,
  `b_t = 1/n_T`. Sinkhorn, convex, no gradients.

**Head importance** `a_s`: measured, not guessed — zero-ablate head `s` and
record the increase in calibration NLL. `n_S` forward passes over a small
calibration slice; embarrassingly parallel.

### 5.3 Transfer, matched `d_h`, RoPE preserved (the v0 case)

Let `A = A_proc` be the conjugation map for the aligned depth pair. We want the
target head to read what the source head read: `Ñ(H_T) W^t ≈ Ñ(H_S) W^s`. Under
`Ñ(H_T) ≈ Ñ(H_S) A` this is a least-squares problem in `W^t`, weighted by the
stream's own second moment `Ḡ = Ñ(H_S)ᵀÑ(H_S)`:

```
Ŵ^t = argmin_W ‖ Ñ(H_S)(A W − W^s) ‖²_F  =  (Aᵀ Ḡ A)⁻¹ Aᵀ Ḡ W^s        …(†)
```

`(†)` collapses to the naive `Aᵀ W^s` exactly when `Ḡ ∝ I`. It never is: on a
synthetic stream with `cond(Ḡ) ≈ 1.6·10⁵` — the right order for an LLM residual
stream with massive-activation channels — `(†)` cuts the conjugation residual
by **76 %** against `AᵀW^s`. `AᵀḠA` is `d_T×d_T`, one Cholesky per depth pair;
there is no reason to use the naive form. (This is the same correction as
Prop. 8, one level up: *a formula that ignores the activation covariance is the
isotropic special case of a better one*.)

Write `A^†` for the **RMSNorm-corrected, activation-weighted pull-back**, which
is the only conjugation operator used anywhere in CAWA:

```
A^†  :=  √(d_S/d_T) · (Aᵀ Ḡ A)⁻¹ Aᵀ Ḡ      ∈ ℝ^{d_T×d_S}
```

Readers are pulled back by `A^†`; writers are pushed forward by `A`:

```
Ŵ_Q^t = A^† W_Q^s      Ŵ_K^t = A^† W_K^s      Ŵ_V^t = A^† W_V^s
Ŵ_O^t = W_O^s A
```

The `√(d_S/d_T)` in `A^†` exactly cancels the `√(d_T/d_S)` of the norm relation,
so attention logits carry **no residual temperature shift** — the constants
cancel on both the query and key side. A global scale `s` may be fitted
alongside `A` (scaled Procrustes); this preserves Prop. 7 because
`(sA)(sA)ᵀ = s²P_A`.

**Head-internal coordinates are never touched, so the RoPE frequency pairing
is preserved exactly.** Consistency check: the induced circuits are
`Ŵ_Q(Ŵ_K)ᵀ = A^† QK_s (A^†)ᵀ` and `Ŵ_V Ŵ_O = A^† OV_s A`, which is the correct
change of basis for a bilinear form and for a linear map respectively.

Error sources, both quantified by the same `ρ` (§4.2): (i) the projector `AAᵀ ≠ I` when `d_T < d_S`; (ii) the per-token scalar
`κ(x) = ‖x‖/‖P_A x‖ ≥ 1`, which rescales attention logits by `κ_i κ_j` — a
per-token-pair **temperature distortion**, vanishing as `ρ → 1` and exactly
zero whenever `d_T ≥ d_S` (Prop. 7's widening case).

### 5.4 Many-to-one: merge OV, select QK (Prop. P4)

```
OV̂_t = Σ_s π_{st} · A^† OV_s A            then truncate to rank d_h^T:
OV̂_t ≈ U_r Σ_r V_rᵀ  ⟹  Ŵ_V^t = U_r Σ_r^{1/2},  Ŵ_O^t = Σ_r^{1/2} V_rᵀ
truncation loss  η = Σ_{k>r} σ_k² / Σ_k σ_k²
```

`QK` is **not** merged: `softmax` is not affine, so the average of two circuits
is not the average of two patterns. Instead `Ŵ_Q^t, Ŵ_K^t` are taken from the
single highest-importance source head assigned to `t` (`argmax_s π_{st}·a_s`).

### 5.5 Mismatched `d_h`

Requires refactoring the circuits, which destroys RoPE's frequency pairing.
**Deferred to v1** (restriction R-4 in §11). The correct v1 treatment is a
RoPE-aware factorisation constrained to 2×2 frequency blocks; unconstrained SVD
here is a known-wrong operation and the code must refuse it rather than
silently produce a broken model.

### 5.6 GQA re-tying — closed form, not an average

Target group `g` shares one `W_K` across query heads `q ∈ g`. Naively averaging
per-head solutions is not least-squares optimal, because logits are bilinear.
But **given `W_Q` fixed, logits are linear in `W_K`**, so the optimal shared key
projection has a closed form. With `P_q = Ñ(X) W_Q^q ∈ ℝ^{n×d_h}`,
`Y = Ñ(X) ∈ ℝ^{n×d}`, and per-head targets `L_q^*`:

```
minimise  Σ_{q∈g} w_q ‖ P_q W_Kᵀ Yᵀ − L_q^* ‖²_F
normal equations:   ( Σ_q w_q P_qᵀP_q ) W_Kᵀ ( YᵀY )  =  Σ_q w_q P_qᵀ L_q^* Y
```

a Sylvester equation, solved exactly by simultaneous diagonalisation of the
`d_h×d_h` and `d×d` Gram matrices. `W_V^{(g)}` is a plain weighted least-squares
average because the V path is linear. Within-group dispersion of the per-head
solutions is recorded as a confidence penalty — MHA→GQA is a genuine
information bottleneck and the confidence must say so.

---

## 6. Neuron correspondence and MLP transfer

### 6.1 Cost

```
C^n[k,l] = a·( 1 − cos(Aᵀg_k , g_l) )                      gate direction, gauge-fixed
         + b·( 1 − ⟨Aᵀu_k o_kᵀA , u_l o_lᵀ⟩_F / (‖·‖‖·‖) ) rank-1 read→write map
         + c·( 1 − corr(a_k^S , a_l^T) )                    activation correlation
```

The middle term factorises: `⟨u_k o_kᵀ, u_l o_lᵀ⟩_F = (u_k·u_l)(o_k·o_l)`, so
the whole `m_S×m_T` cost is three matrix products, never `m²` outer products.

This is the brief's `score = a·incoming + b·outgoing + c·activation` — but with
the incoming/outgoing terms replaced by their gauge-invariant forms. The naive
version (`cos(u_k, u_l)` and `cos(o_k, o_l)` separately) is scale-gauge
dependent and would score two *identical* neurons at arbitrary similarity.

### 6.2 Assignment

Hungarian when `m_S = m_T`; entropic OT with importance marginals otherwise.
Importance `a_k = E[|a_k|]·‖o_k‖` — the neuron's expected write magnitude into
the stream, which is the quantity that actually matters for the residual stream.

### 6.3 Transfer

With `W_g, W_u ∈ ℝ^{d×m}`, `W_d ∈ ℝ^{m×d}` and `Π ∈ ℝ^{m_S×m_T}`:

```
Ŵ_g^t = A^† W_g^S Π       Ŵ_u^t = A^† W_u^S Π       Ŵ_d^t = Πᵀ W_d^S A
```

Shapes: `A^† ∈ ℝ^{d_T×d_S}`, so `(d_T×d_S)(d_S×m_S)(m_S×m_T) = d_T×m_T` ✓, `(m_T×m_S)(m_S×d_S)(d_S×d_T) = m_T×d_T` ✓.

**Merging caveat.** For a soft `Π` this averages gate directions across merged
neurons. `σ(x·(g₁+g₂)/2) ≠ (σ(x·g₁)+σ(x·g₂))/2` — merging gates is
nonlinear-invalid, exactly as for `QK`. Therefore: for `m_S > m_T`, **select**
the top-`m_T` source neurons by importance for `(g, u)`, and use the closed-form
re-fit of §7 to let `W_d` absorb what the discarded neurons were contributing.
This is where the re-fit earns its place — it is the only mechanism that can
compensate for a discarded component.

---

## 7. Parameter transplantation — the improved equation

### 7.1 Why the brief's equation is a special case

The brief proposes `W_T' = (1−λ)W_T + λ·P_out Π W_S P_in`. CAWA replaces this
with a **data-aware ridge toward the target**, and the brief's form falls out
as a corner case.

Let `Φ ∈ ℝ^{n×m}` be the block's pre-output features **under the target's own
current input** (post-activation MLP features, or concatenated head outputs),
and `Y* ∈ ℝ^{n×d}` the desired residual increment. Solve

```
W* = argmin_W  ‖Φ W − Y*‖²_F + μ‖W − W_T‖²_F
   = ( ΦᵀΦ + μI )⁻¹ ( ΦᵀY* + μ W_T )                    …(★)
```

**Proposition 8.** *If `ΦᵀΦ = cI` and `Y* = Φ Ŵ_S`, then*
`W* = λ Ŵ_S + (1−λ) W_T` *with* `λ = c/(c+μ)`.

**Proof.** `ΦᵀY* = c Ŵ_S`, so `W* = (c+μ)⁻¹(c Ŵ_S + μ W_T)`. ∎

So the brief's interpolation is (★) under the assumption that the block's input
covariance is isotropic. It is not: LLM feature covariances are extremely
anisotropic. (★) weights each direction by how much calibration energy it
carries, which is precisely the correction the isotropic form omits — and it is
the same estimator that GPTQ/SparseGPT use to modify LLM weights successfully
without gradients.

`ΦᵀΦ` and `ΦᵀY*` are accumulated streaming, `O(m²)` and `O(md)` memory;
`μ = α·tr(ΦᵀΦ)/m`; solved by Cholesky with the damping-retry loop.

### 7.2 The transfer target `Y*`

Function-space interpolation, not parameter-space:

```
Y* = (1 − λ) · Y_T  +  λ · ( Δ_S⁽ⁱ⁾ A )
```

where `Y_T` is the target block's *current* increment and `Δ_S⁽ⁱ⁾ A` is the
source block's increment mapped into the target stream. Interpolating the
function and then solving for weights strictly dominates interpolating weights,
because it accounts for what the block's own input actually is.

### 7.3 Sequential application with error feedback

Blocks are processed in depth order and **the target's activations are
recollected after every accepted edit**, so block `j+1` is fitted against the
stream the modified model actually produces. Without this, errors compound
silently; with it, later blocks partially absorb earlier blocks' residuals.
This is the same error-feedback structure that makes SparseGPT work at
billion-parameter scale, and it is not optional.

### 7.4 Norm and spectrum guardrails

Downstream layers are calibrated to a particular residual-stream scale. After
solving (★), rescale so the block's increment RMS is preserved:

```
W* ← W* · min( 1, ρ_norm · RMS(Y_T) / RMS(Φ W*) )       ρ_norm = 1.05 default
reject if ‖W*‖₂ > ρ_spec ‖W_T‖₂                          ρ_spec = 1.25 default
reject if ‖W* − W_T‖_F / ‖W_T‖_F > ρ_dev                 ρ_dev  = 0.35 default
```

### 7.5 Norm-parameter transfer

After C1 canonicalisation there are no gains to transfer — they live inside the
readers. CAWA therefore emits models in **gain-folded canonical form**
(`γ = 1`, shapes unchanged, functionally identical), optionally re-splitting
afterwards for numerical hygiene: pick `γ′_c = ‖(diag(γ)W)_{c,:}‖ / mean_c(·)`
and set `W′ = diag(γ′)⁻¹ diag(γ) W`. This keeps the emitted checkpoint loadable
by stock `transformers` with no code changes.

### 7.6 Rung 3 — CAWA-LR, the closed-form low-rank correction

When full transplantation is rejected (which §5 of the research analysis
predicts will be common), fall back to a **rank-r additive correction computed
in closed form**. Let `R = Y* − Φ W_T` be the residual the target fails to
produce. Solve the reduced-rank ridge regression

```
min_{U∈ℝ^{m×r}, V∈ℝ^{r×d}}  ‖Φ(W_T + UV) − Y*‖²_F + μ‖UV‖²_F
```

whose exact solution is the rank-`r` truncation of the full ridge solution in
the `ΦᵀΦ`-metric (Izenman's reduced-rank regression theorem):

```
W_full = (ΦᵀΦ + μI)⁻¹ Φᵀ Y*
M      = (ΦᵀΦ + μI)^{1/2} (W_full − W_T)
M      = U_M Σ_M V_Mᵀ   (thin SVD)
UV     = (ΦᵀΦ + μI)^{−1/2} U_M[:, :r] Σ_M[:r] V_M[:r, :]ᵀ
```

Properties: never changes shapes; deviation bounded by construction
(`‖UV‖_F` is directly controllable via `r` and `μ`); produces a LoRA-shaped
delta with **no gradient step anywhere**. This is the most likely rung to
produce a measurable improvement, and it is a legitimate CAWA output rather
than a consolation prize — the alignment machinery is what defines `Y*`.

---

## 8. Confidence

Confidence is a **gate on how much a transfer is allowed to change**, not the
transfer amount itself (see §9). Four independent factors, each in `[0,1]`:

```
c_depth[i,j] = softmax_j( −C[i,j]/τ_d )                normalised DP margin
c_match      = 1 − p_perm                              permutation test, below
c_proj       = ρ · R²(A)                               retained energy × fit
c_struct     = shape compatibility ∈ {1, …}            1 if exact; ρ_h·ρ_m otherwise
c            = ( c_depth · c_match · c_proj · c_struct )^{1/4}      geometric mean
```

**Permutation test for `c_match`.** Given the matching cost matrix `C` and the
achieved assignment cost `c̄_match = mean_k C[k, π(k)]`, the null distribution of
a *random* assignment has mean `μ₀ = mean(C)` and variance
`σ₀² = var(C)/min(m_S,m_T)`. Then `z = (μ₀ − c̄_match)/σ₀` and
`p_perm = Φ(−z)`. This answers the right question — *is this matching better
than chance?* — with a number that means something. A matching indistinguishable
from random (`z < 2`) should transfer nothing, however good its raw cosines
look.

The geometric mean (rather than a product) keeps `c` from collapsing to zero
when one factor is merely mediocre, while still letting any single near-zero
factor veto the transfer.

---

## 9. λ — chosen by measurement, not by a formula

The brief asks for a principled `λ = f(confidence)`. The principled answer is
that **no formula can be correct**, and here is why.

Under the signal+noise model `Ŵ_S = W° + ε_S`, `W_T = W° + ε_T` with
independent noise, the MSE-optimal interpolation is the James–Stein weight

```
λ* = σ_T² / (σ_S² + σ_T²)
```

This requires a **common true parameter `W°`** — which exists for two fine-tunes
of one base model, and does **not** exist for two independently trained models.
In the regime CAWA targets, the model justifying a closed-form λ does not hold,
so a closed-form λ would be a formula with no referent.

CAWA therefore uses confidence to **bound** λ and measurement to **choose** it:

```
λ_max = c^β                       β = 1.5 default; c below c_min ⇒ skip block entirely
λ*    = argmin_{λ ∈ [0, λ_max]} NLL_holdout( T with this block transplanted at λ )
```

by golden-section search, ~6 forward evaluations per block on a small held-out
calibration slice. Forward passes only — no gradients, fully within the brief's
constraints. This is strictly more honest than a hand-designed `f(c)`: it
optimises the thing we actually care about instead of a proxy for it.

---

## 10. Acceptance, rollback, and the false-positive problem

### 10.1 Per-block acceptance

After transplanting block `j`, on a **held-out** calibration split `H` (disjoint
from the fitting split and from the final reporting split):

```
accept  ⟺   p_paired( NLL_H(T') < NLL_H(T) ) < α/L      (Bonferroni over L blocks)
        ∧   KL( T'(·|x) ‖ T(·|x) ) < κ_max averaged over H
        ∧   all §7.4 guardrails pass
        ∧   attention entropy of every edited head within [ē/3, 3ē]  (sink-collapse check)
otherwise rollback: restore the CPU copy of the block, record the failure reason
```

`p_paired` from a paired bootstrap over documents (10⁴ resamples), not a naive
mean comparison — per-document NLL is heavy-tailed and a mean difference will
declare significance on noise.

### 10.2 The greedy-overfitting trap, and its control

Greedy accept-if-better over ~30 blocks, each evaluated on the same held-out
slice, **will** produce apparent gains from noise. Two mandatory controls:

1. **Three-way split.** Fit / accept / report. The final number is reported on
   data never used for a single accept decision.
2. **Shuffled-source null run.** Run the entire pipeline with the source's
   block index randomly permuted (destroying the correspondence but preserving
   every distributional property of the weights). The number of blocks accepted
   under this null is the empirical false-acceptance rate. **If the null run
   accepts a comparable number of blocks to the real run, the pipeline is
   measuring noise and the result is void.** This control is cheap and is the
   difference between a result and a press release.

---

## 11. Restrictions of v0 — stated explicitly (brief §3)

| # | Restriction | Lifted in |
|---|---|---|
| R-1 | Identical tokenizer and vocabulary | never (A3 out of scope) |
| R-2 | `d_S = d_T` and `E_S = E_T` (assumption A0) | v2 → A1/A2 via `A_E` |
| R-3 | RMSNorm (pre-norm), no stream biases | v2 (LayerNorm via Prop. 1′ centering fold) |
| R-4 | `d_h^S = d_h^T`, identical RoPE base and scaling | v1 (RoPE-aware refactorisation) |
| R-5 | Same activation family within a pair (SwiGLU↔SwiGLU, GELU↔GELU) | v2 |
| R-6 | Dense FFN only — no MoE | not planned |
| R-7 | Standard MHA/GQA — no MLA, no sliding-window-only attention | v3 |
| R-8 | Varying: `L`, `m` (intermediate), `n_kv` (GQA groups) | — this is what v0 *does* support |

v0's supported difference set (R-8) is exactly the structured-pruning axis,
which is what makes the E3 testbed (§04-experiments) the natural first target:
it satisfies A0 **exactly** while the architectures genuinely differ.

---

## 12. Numerical stability checklist

| Risk | Treatment |
|---|---|
| bf16 weight round-trip | all alignment math in fp32; fp64 for `d ≤ 4096` Cholesky on CPU |
| ill-conditioned `Ḡ` | damping `μ = α tr(Ḡ)/d`, GCV-selected `α`; retry ×10 on Cholesky failure |
| unstable `pinv` | never used — Cholesky or SVD with an explicit `rcond` floor |
| outlier channels | per-channel standardisation `D`, map recovered as `D_S⁻¹ Ã D_T` |
| large activation matrices | second-moment accumulation only; never store `n×d` |
| `d×d` circuit SVDs | factored traces (§2.1); randomised SVD only if a full circuit is unavoidable |
| GPU memory | one model resident at a time; source statistics collected, model evicted, target loaded |
| accumulation drift | Kahan or fp64 accumulators for `n > 10⁷` tokens |
| degenerate singular subspaces | detect `σ_k/σ_{k+1} < 1+δ`; canonical factorisation is non-unique there — flag, do not transfer |

The "one model resident at a time" rule matches Mesbah's existing training
constraint (root `CLAUDE.md`), so CAWA runs on the same 16 GB dev box.
