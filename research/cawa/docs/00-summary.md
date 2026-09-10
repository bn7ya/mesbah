# CAWA · Design summary

Direct answers to the twelve questions of the brief's §25, each pointing at the
document that derives it. Read this first; read `01` next.

---

### 1. CAWA, restated mathematically

Given source `S` and target `T`, both decoder-only transformers over a shared
vocabulary, find

```
T' = Adapt(S, T, D_calib)      s.t.  Arch(T') = Arch(T)
```

minimising `E_{x~D}[ −log p_{T'}(x) ]`, where `Adapt` is composed exclusively of
closed-form linear algebra, combinatorial assignment, and forward passes.

The object being manipulated is not the weight tensor. Writing
`H⁽ˡ⁺¹⁾ = H⁽ˡ⁾ + Δ⁽ˡ⁾`, CAWA seeks, for each target block `j` and its aligned
source blocks `I_j`, parameters `θ_j` of `T`'s block that minimise

```
E ‖ f_{θ_j}(H_T⁽ʲ⁾)  −  [ (1−λ)·Δ_T⁽ʲ⁾ + λ·(Σ_{i∈I_j} Γ_{ij} Δ_S⁽ⁱ⁾) A_ij ] ‖²
```

subject to guardrails on `‖θ_j − θ_j^orig‖`, where `A_ij` is a stream map,
`Γ` a monotone depth-alignment plan, and `λ` a confidence-bounded intensity.
**This is function-space matching in the residual stream, with weights as the
output rather than the input.** → `01` §6, `02` §7.

---

### 2. The hardest theoretical problems

1. **The residual streams share no basis beyond layer 0** — and because
   `H⁽⁰⁾` is *literally identical*, every naive similarity metric reports
   spurious early agreement. Mandatory control: `ExcessAlign`. → `01` §3-P1
2. **The dimensional bottleneck is an information bound.** `d_T < d_S` makes the
   transplant blind to a `(d_S−d_T)`-dimensional subspace; fidelity is capped by
   the effective rank of the source's stream, a property measurable before any
   code is written. → `01` §3-P2
3. **RMSNorm does not commute with non-conformal maps.** `Ñ(xA) = Ñ(x)A` iff
   `AᵀA = c²I`, so the best-fitting stream map is the *wrong* map for weight
   conjugation. → `01` §3-P3
4. **Attention patterns cannot be merged.** Softmax is not affine; the average
   of two `QK` circuits is not the average of two patterns. → `01` §3-P4
5. **Alignment quality ≠ functional benefit.** Transfer helps only when the
   source has a capability the target lacks *and* it survives the projection.
   For two comparable models it will not. → `01` §3-P5

---

### 3. What is solvable in closed form

Depth alignment (DP), head and neuron matching (Hungarian / Sinkhorn), stream
maps (ridge, Procrustes, CCA), output-weight re-fit (ridge), low-rank correction
(reduced-rank regression), confidence (regression residuals + permutation test).
The *joint* problem is nonconvex and is solved by **alternating exact steps** —
monotone, terminating, no gradients. λ selection and acceptance use forward
passes only. → `01` §7

---

### 4. How identical embeddings help — and how they do not

**They help far more than expected in one way, and not at all in the way the
brief assumes.**

- **Proposition 2:** `E_S = E_T` with full column rank ⟹ the only residual
  gauge element is `Q = I`. The shared embedding does not help you *find* a
  hidden rotation — it proves **there is none to find**. The models are already
  co-registered at layer 0.
- **Corollary:** therefore every mismatch at depth > 0 is genuine functional
  divergence, and every alignment map is a lossy approximation with a real
  error budget.
- **It also gives** a shared, data-free interpretive basis: the **cross-model
  logit lens**, which yields a *functional* depth-correspondence metric in
  units of next-token belief.
- **It does not give** comparability of `W_Q/W_K/W_V/W_O` (the head-internal
  `GL(d_h)` gauge survives), nor anything about neuron indices, nor anything
  about layers > 0.
- **The assumption as written is self-contradictory**: `E_S = E_T` forces
  `d_S = d_T`, which the brief's §3 requirement for differing hidden dimensions
  forbids. The anchor that generalises is the shared **vocabulary**: `E_S` and
  `E_T` are row-paired, giving a `|V|`-example closed-form regression
  `A_E = (E_SᵀE_S+μI)⁻¹E_SᵀE_T` with no calibration data at all. → `01` §2

---

### 5. Best representation-alignment mechanism

A hybrid depth cost — `CKA` (coarse, rotation-invariant) + **cross-model
logit-lens JS** (functional) + **constrained regression `R²`** (the quantity
that actually bounds transfer error) + a relative-depth prior — resolved by
monotone DTW.

And a deliberate argument **against** the brief's preference for CKA: under
Prop. 2 the gauge is already fixed, so CKA's rotation invariance *discards
usable information* and can report high similarity for an alignment no
transplant can realise. Report the gap `CKA − R²_identity` as an
over-reporting warning. → `02` §3

---

### 6. Normalised architecture graph

A **circuit-level IR** whose nodes are gauge-invariant objects, not tensors:
per head `QK = W_Q W_Kᵀ` and `OV = W_V W_O` in canonical factorisation, per
neuron `ν = (g, u oᵀ)`, all after an exact canonicalisation pass (gain folding,
centering folding, bias folding, GQA→MHA expansion). Adapters must pass a
`writeback(lift(m)) ≡ m` logit-equality test before they are allowed to modify
anything. → `03` §1

---

### 7. Layer / head / neuron correspondence

- **Layers:** monotone DTW over the hybrid cost, `O(L_S L_T)` exact, with a
  relative-depth band; many-to-one via the transport plan `Γ`.
- **Heads:** Hungarian (balanced) or unbalanced Sinkhorn OT on
  `α·d_QK + β·d_OV + γ·d_attn`, all gauge-invariant, with importance measured
  by ablation. **Merge OV (linear), select QK (nonlinear).**
- **Neurons:** Hungarian / OT on gate-direction cosine + rank-1 `⟨u_k o_kᵀ, u_l o_lᵀ⟩`
  (which factorises to `(u_k·u_l)(o_k·o_l)`) + activation correlation.
  → `02` §§3, 5, 6

---

### 8. Parameter-transplantation equations

Conjugation with a semi-orthogonal `A`, head-internal coordinates untouched so
**RoPE is preserved exactly**:

```
A^† = √(d_S/d_T)·(AᵀḠA)⁻¹AᵀḠ        (activation-weighted, RMSNorm-corrected)

Ŵ_Q = A^† W_Q^S   Ŵ_K = A^† W_K^S   Ŵ_V = A^† W_V^S   Ŵ_O = W_O^S A
Ŵ_g = A^† W_g^S Π Ŵ_u = A^† W_u^S Π Ŵ_d = Πᵀ W_d^S A
```

Then — and this is the substantive improvement on the brief's equation — the
**output-side maps are never copied, they are solved**:

```
W* = (ΦᵀΦ + μI)⁻¹ (ΦᵀY* + μ W_T)          Y* = (1−λ)Δ_T + λ·(Δ_S A)
```

**Proposition 8:** the brief's `W' = (1−λ)W_T + λ P_out Π W_S P_in` is exactly
this ridge under `ΦᵀΦ = cI`. Real LLM feature covariances are extremely
anisotropic, so the isotropic form is provably the wrong estimator. → `02` §7

---

### 9. The smallest falsifying experiment

**E0 — the mappability atlas.** No transfer code, no weight modification, one
afternoon:

- **E0-a** solve `E_S A ≈ E_T` in closed form (five minutes, no GPU) — measures
  the anchor's real strength.
- **E0-b** for every depth pair, report `R²` of identity / Procrustes /
  unconstrained maps, CKA, retained energy `ρ`, and above all
  **`ExcessAlign = R²(H_S⁽ⁱ⁾→H_T⁽ʲ⁾) − R²(H⁽⁰⁾→H_T⁽ʲ⁾)`**.
- **E0-c** closed-form ridge **stitch** as the oracle: the ceiling on any
  linear-map-based transfer.

**Kill criterion:** `max ExcessAlign < 0.10` and a poor oracle stitch ⟹ H1a is
false for that pair and no linear-stream-map method can work on it. → `04` §E0

---

### 10. Closest research, and the difference

| Neighbourhood | Difference |
|---|---|
| Git Re-Basin / OT Fusion / ZipIt! | they need **identical architectures** and match raw neurons; CAWA matches **gauge-invariant circuits** across different shapes, and solves rather than averages |
| Soups / TIES / DARE / task arithmetic / **RegMean** | need a **common parameter space**; RegMean is essentially CAWA's re-fit step *without* matching or projection — so it belongs in the **baseline table** |
| GPTQ / SparseGPT / AWQ / **SliceGPT** | reconstruct a model against **itself**; SliceGPT uses exactly our Prop. 1 invariance. This is the neighbourhood that proves the mechanism scales without gradients, and CAWA is built on its primitive |
| CKA / stitching / relative representations / logit lens | measurement, or stitching with a **trained** layer; CAWA's stitch is closed-form and used as an oracle, and it uses the logit lens **cross-model** as an alignment cost |
| FuseLLM / weight subcloning / Minitron / LLM-Pruner | all end in **gradient training**. Weight subcloning is the closest relative and needs training to be useful — **CAWA is the question of how far that mapping goes when training is not allowed** |

→ `05`

---

### 11. Feasibility (probability of significant held-out NLL improvement, no gradients, null-controlled)

| Class | Score |
|---|---:|
| Same architecture / different sizes | **45** |
| Closely related architectures | **25** |
| Substantially different transformer architectures | **8** |
| Arbitrary neural architectures | **2** |
| — *separate axis:* **structured-pruning recovery** (`d`, `E` preserved — the only case satisfying the brief's mandatory assumption *with* real architectural difference) | **70** |
| — *softer:* the E0 measurement is worth publishing regardless of outcome | **90** |

→ `06`

---

### 12. Recommendation before implementation

Do **not** build the full pipeline first. Build **E0**, gate on it (G1), and
treat block transplantation as the hypothesis under test rather than the
product under construction. `02` and `03` are complete enough to implement in
full when the gate passes; implementing them before it would spend weeks
learning what an afternoon can tell us.

---

## Verification

Every proposition above is checked numerically by
[`../verify_design_claims.py`](../verify_design_claims.py) (numpy only, seconds
to run): the `O(d)` residual gauge on a real two-block forward pass, the
`GL(d_h)` OV gauge, the RoPE torus and the failure of general `GL(d_h)` under
RoPE, the MLP neuron gauge and the *non*-freedom of gate scaling, Prop. 7 and
its widening/narrowing asymmetry, the 86 % gain from activation-weighted
conjugation, Prop. 8 in both regimes, the CAWA-LR closed form against
alternating least squares, and the streaming CKA identity. **18/18 pass.**

---

## The three corrections this design makes to the brief

1. **Head similarity from `W_Q, W_K, W_V, W_O` is mathematically invalid.**
   `W_V` and `W_O` are pure `GL(d_h)` gauge — two heads computing the identical
   function can have `W_V` cosine similarity 0. Use `QK` and `OV` circuits.
2. **`E_S = E_T` and "different hidden dimensions" cannot both hold.** Use the
   shared *vocabulary* (row-paired embeddings, closed-form `A_E`) as the
   general anchor, and reserve strict `E_S = E_T` for constructed pairs — where
   it is the cleanest testbed in the project.
3. **`W' = (1−λ)W_T + λ·P_out Π W_S P_in` is the isotropic special case of a
   data-aware ridge**, and LLM activations are never isotropic. Solve for the
   output-side weights instead of interpolating them.

Plus one addition the brief's §17 asks for but does not specify: **the
`ExcessAlign` control and the shuffled-source null run**, without which this
class of method will confidently report a false positive.
