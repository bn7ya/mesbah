# CAWA · Related work, and precisely how CAWA differs

> **Status: from working knowledge.** Every claim about a specific paper must be
> re-verified against the primary source before it appears in a write-up.
> Treat this as a map of the territory, not as citable text.

---

## 1. The five neighbourhoods

### 1.1 Permutation-symmetry model merging — *the closest in spirit*

| Work | What it does |
|---|---|
| Entezari et al. 2022 | conjectures that permutation symmetry explains linear mode connectivity |
| Ainsworth et al. 2023 (**Git Re-Basin**) | matches neurons by weight/activation cost, permutes, then averages |
| Singh & Jaggi 2020 (**OT Fusion**) | soft OT matching instead of hard permutation |
| Imfeld et al. 2024 (**Transformer Fusion with OT**) | extends OT fusion to transformer specifics |
| Verma & Elbayad 2024 | re-basin for text transformers from different initialisations |
| Stoica et al. 2024 (**ZipIt!**) | matches *features* within and across models, merges partially, leaves the rest unmerged |

**Shared with CAWA:** the insight that neuron identity is a gauge and must be
matched before anything is combined; Hungarian/OT machinery.

**How CAWA differs:**
1. These assume **identical architectures**. CAWA's problem starts where theirs
   ends — different `L`, `m`, head counts, and (at A2) different `d`.
2. They match at the level of *weight matrices and neurons*. CAWA matches
   **gauge-invariant circuits** (`QK`, `OV`, `(g, uoᵀ)`), which is strictly
   necessary for attention: a `W_V`-based cost is measuring `GL(d_h)` gauge
   (Prop. 3). To our knowledge no merging paper does head matching in circuit
   space.
3. They **average**. CAWA **solves** — the final step is a closed-form
   regression against calibration activations, not an interpolation.
4. Their empirical record on transformer LMs is weak; CAWA takes this as a
   *prediction* (experiment E4) rather than a problem to be engineered around.

### 1.2 Parameter-space merging (soups, task arithmetic, TIES, DARE, RegMean)

| Work | What it does |
|---|---|
| Wortsman et al. 2022 (**Model soups**) | average fine-tunes of one base |
| Ilharco et al. 2023 (**Task arithmetic**) | `θ_base + Σ τ_i` with task vectors |
| Matena & Raffel 2022 (**Fisher merging**) | Fisher-weighted average |
| Yadav et al. 2023 (**TIES**), Yu et al. 2024 (**DARE**) | sparsify/resolve sign conflicts before averaging |
| **Jin et al. 2023 (RegMean)** | **closed-form least-squares merging using per-layer inner-product matrices** |

**How CAWA differs:** all of these require a **common parameter space** — same
architecture, usually a common ancestor. The brief's §24 is right that these are
baselines and not the goal. **RegMean is the most important of them for us**:
it is a *dataless-except-for-Gram-matrices, closed-form, least-squares* merge,
and it is essentially CAWA's re-fit step (`02` §7) applied to same-shaped
models with no matching or projection. CAWA should be read as "RegMean, but
across architectures, with the alignment problem solved first" — and RegMean
therefore belongs in the baseline table, not the related-work section alone.

### 1.3 Closed-form, gradient-free weight modification — *the strongest precedent*

| Work | What it does |
|---|---|
| Frantar & Alistarh 2023 (**GPTQ**, **SparseGPT**) | layer-wise `min ‖XW − XŴ‖` with Hessian-based closed-form updates + error feedback |
| Lin et al. 2024 (**AWQ**) | activation-aware scaling, closed form |
| Sun et al. 2024 (**Wanda**) | activation-weighted magnitude pruning, no gradients |
| Ashkboos et al. 2024 (**SliceGPT**) | exploits RMSNorm computational invariance (our Prop. 1) to rotate and slice |
| **QuaRot**, **SpinQuant** 2024 | same `O(d)` invariance, used to kill quantisation outliers |

**Shared with CAWA:** the layer-wise closed-form reconstruction primitive and
the error-feedback loop; and, in SliceGPT/QuaRot, *exactly the rotational gauge
CAWA formalises in Prop. 1*.

**How CAWA differs:** these methods reconstruct a model against **itself**
(compressed vs. original). CAWA reconstructs a target against a **different
model with a different architecture**, which requires the entire correspondence
apparatus they do not need. But this is the neighbourhood that proves the
*mechanism* works at scale without gradients, and it is why `02` §7 is built on
their primitive rather than on parameter interpolation.

### 1.4 Representation similarity and stitching

| Work | What it does |
|---|---|
| Kornblith et al. 2019 (**CKA**), Raghu 2017 (**SVCCA**), Morcos 2018 (**PWCCA**) | measure cross-model representation similarity |
| Lenc & Vedaldi 2015; Bansal et al. 2021 | **model stitching** — join two nets with a *trained* linear layer |
| Moschella et al. 2023 (**Relative representations**) | encode via similarity to **shared anchors** to get a common latent space |
| Huh et al. 2024 (**Platonic Representation Hypothesis**) | models converge to similar representations |
| Anthropic 2024 (**sparse crosscoders / model diffing**) | match features across models |
| nostalgebraist 2020 (**logit lens**) | read intermediate states through the unembedding |

**How CAWA differs and what it borrows:** CAWA's `C^lens` layer-correspondence
metric is the logit lens used *cross-model* as an alignment cost — enabled by
the shared vocabulary, and we are not aware of prior use of it for this. The
**relative-representations** idea is the closest conceptual cousin to the
brief's "shared embedding as anchor", and CAWA's Prop. 2 sharpens it: with an
identical embedding matrix you do not need relative encodings, because the
absolute basis is already shared. Stitching is CAWA's **oracle** (E0-c), and
the key difference is that CAWA's stitch is *closed-form*, so it stays inside
the no-gradient constraint.

CAWA also **argues against** the default use of CKA here: rotation invariance
discards exactly the information Prop. 2 provides (`01` §3, `02` §3.1).

### 1.5 Cross-model knowledge transfer and pruning recovery

| Work | What it does |
|---|---|
| Wan et al. 2024 (**FuseLLM / FuseChat**) | fuse LLMs with different tokenizers by distilling aligned output distributions |
| Samragh et al. 2023 (**Weight subcloning**) | initialise a smaller transformer from a larger one, then train |
| Muralidharan et al. 2024 (**Minitron**) | structured prune + distil |
| Ma et al. 2023 (**LLM-Pruner**) | structured prune + LoRA recovery |
| Men et al. 2024 (**ShortGPT**), Yang et al. 2024 (**LaCo**) | layer-level redundancy and collapse |
| Akiba et al. 2024 | evolutionary merging across model families |

**How CAWA differs:** every one of these ends in **gradient training**
(distillation, LoRA recovery, or continued pretraining) — which the brief
forbids. Weight subcloning is structurally the closest relative: it maps a
larger model's parameters into a smaller architecture by importance ranking,
and then *requires training to be useful*. **CAWA is the question "how far can
that mapping go if training is not allowed?"** Evolutionary merging is
gradient-free but is black-box *search*, not analysis — it needs thousands of
evaluations where CAWA needs closed-form solves.

---

## 2. CAWA's distinct claims, stated so they can be checked

1. **Circuit-level gauge correctness.** Head correspondence computed on `QK`
   and `OV` rather than on `W_Q, W_K, W_V, W_O`, with the `GL(d_h)` /
   RoPE-torus gauge derived rather than assumed away.
2. **The shared embedding as a gauge-elimination result, not a similarity
   heuristic** (Prop. 2), together with its corollary that residual mismatch is
   real divergence — and the `ExcessAlign` control that follows from it.
3. **Cross-model logit-lens depth alignment** — a functional layer-matching
   metric in units of next-token belief, available only under a shared vocabulary.
4. **Merge-OV / select-QK**, from the observation that softmax makes attention
   patterns non-mergeable while OV circuits are linear and mergeable.
5. **Transfer as closed-form functional re-fit** (`02` §7), with Prop. 8 showing
   the standard interpolation equation to be its isotropic special case.
6. **Confidence gates, measurement decides** — λ chosen by held-out search
   inside a confidence-derived bound, with a permutation test giving matching
   confidence a real null.
7. **The shuffled-source null run** as a mandatory control against the greedy
   accept-if-better overfitting that this class of method invites.

Claims 1, 3, 4 and 7 are, as far as we currently know, not present in the
literature above. Claims 2 and 5 are sharpenings of known results
(SliceGPT's invariance; RegMean/SparseGPT's regression) applied to a problem
they were not built for. **This list is a research bet, not a priority claim**
— a proper literature search is a prerequisite to any write-up, and any of
these may turn out to exist.
