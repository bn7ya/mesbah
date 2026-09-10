# CAWA · Feasibility assessment and decision gates

---

## 1. What "feasible" is being scored

A score of *n*/100 is the estimated probability that, for a pair in that class,
CAWA produces:

> a **statistically significant reduction in held-out NLL** of the target model
> on a REPORT split never used for any accept decision, with **no gradient
> step anywhere**, **no architecture change**, and a **shuffled-source null run
> that does not reproduce the effect**.

That is a deliberately strict bar. Softer outcomes (a better initialisation for
later training, a useful diagnostic, a good pruning-recovery method) are scored
separately in §3, and they are much more likely.

These are **priors, recorded before E0**, so that they can be scored against
outcomes rather than adjusted after them.

---

## 2. Scores (brief §25.11)

| Class | Score | Reasoning |
|---|---:|---|
| **Same architecture, different sizes** (same family, same tokenizer, e.g. Pythia 410M→160M, Qwen3 4B→1.7B) | **45** | Prop. 2 gives a clean anchor and a real capability gap exists (P5's precondition holds). But `d_S ≠ d_T` triggers the P2 information bottleneck and Prop. 7's RMSNorm tax simultaneously. Most of the probability mass sits on CAWA-LR (rung 3) succeeding while full block transplant fails. |
| **Closely related architectures** (both Llama-like, shared tokenizer, differing `d`, `L`, heads, GQA vs MHA) | **25** | Everything above, plus the anchor degrades from A0 to A2 (`E_S ≠ E_T`, only row-paired), plus GQA re-tying is a genuine bottleneck. The matching machinery has more to do and less to work with. |
| **Substantially different Transformer architectures** (different norms, activations, positional schemes) | **8** | R-3/R-4/R-5 all lifted at once. Different positional encodings in particular break the head-transfer equations at their foundation: RoPE-safety in `02` §5.3 depends on the head-internal basis being shared, which fails across positional schemes. Expect H1a itself to be marginal here. |
| **Arbitrary neural architectures** (CNN ↔ transformer, SSM ↔ transformer, etc.) | **2** | No shared residual stream, no shared read/write structure, no shared basis. What remains is behavioural matching, which is distillation, which needs gradients. The 2 covers a narrow SSM↔transformer case where both are residual token-mixers over a shared vocabulary — and even there the mixing operators have no correspondence. |

### 2.1 A separate axis: the *inverse* problem is much easier

Scored against the same strict bar, but for the pruning-recovery direction
(experiment E3, where `T` is a damaged version of `S`, assumption A0 holds
exactly, and the capability gap is large and known):

| Class | Score |
|---|---:|
| **Structured-pruning recovery, `d` and `E` preserved** | **70** |

This is the highest-value target in the project and the only one where a
positive result is more likely than not. It is also the class that satisfies the
brief's mandatory assumption `E_S = E_T` *simultaneously with* genuine
architectural difference — which no off-the-shelf pair does.

---

## 3. Softer outcomes, scored separately

| Outcome | Score |
|---|---:|
| CAWA produces a **measurement** worth publishing (the E0 mappability atlas: how much of one LLM's stream is linearly recoverable in another's, controlled for the shared embedding) | **90** |
| CAWA produces a **better initialisation** for subsequent QLoRA training than the target alone (measured by loss after a fixed small budget) | **60** |
| CAWA's structural matching contributes **beyond** what the closed-form re-fit contributes alone (i.e. baseline 5 in `04` does not match it) | **30** |
| Full block transplantation between two independently trained, comparable-quality LLMs improves the target | **5** |

The third row is the one that decides whether this is a paper about
cross-architecture transplantation or a paper about closed-form reconstruction
with a good target. The ablation that answers it (`re-fit off/on` × `matching
off/on`) costs almost nothing and should be run early.

---

## 4. What would change these numbers

Upward:
- `ExcessAlign > 0.3` at mid-depth in E0-b — would mean genuinely shared
  computation, not just a shared embedding, and would roughly double rows 1–2.
- `erank(Cov(H_S))` turning out to be `≲ d_T` — would remove the P2 bottleneck
  for the cross-width case. (Unlikely; LLM residual spectra are heavy-tailed
  but not low-rank.)
- The oracle stitch (E0-c) coming close to `min(NLL_S, NLL_T)` — would show the
  linear-map ceiling is high.

Downward:
- `R²_procrustes ≪ R²_ridge` by a large margin (Prediction P-b4) — the RMSNorm
  tax would be worse than assumed and every transplant equation would inherit it.
- The shuffled-source null accepting as many blocks as the real run — would
  invalidate the acceptance procedure and require redesigning it before any
  result means anything.

---

## 5. Decision gates

The project proceeds through gates, not phases. Each gate is a preregistered
number, and failing one means **stopping and reporting**, not tuning until it
passes.

| Gate | Test | Pass condition | On failure |
|---|---|---|---|
| **G0** | E0-a embedding anchor | `R²(A_E) > 0.5` for the chosen pair | switch to an A0 (constructed) pair |
| **G1** | E0-b `ExcessAlign` | `max_{i,j} ExcessAlign > 0.10` | H1a false for the pair — report, try another; if it fails for all, report that as the finding |
| **G2** | E0-c oracle stitch | within 20 % NLL of `min(NLL_S, NLL_T)` at some `(i,j)` | linear transfer ceiling is too low — drop rungs 1–2, go straight to CAWA-LR |
| **G3** | E1 synthetic recovery | all of E1-a…f pass | the implementation is wrong; fix before touching real models |
| **G4** | E1-f + E3 null run | null accepts `< 20 %` of what the real run accepts | acceptance procedure is measuring noise; redesign it |
| **G5** | E3 pruning recovery | significant NLL improvement over `T` on REPORT | the strongest case failed; scores in §2 are all overestimates — report and stop |
| **G6** | E2 same-family | significant NLL improvement over `T` | the general case fails; report E3 as the scope of the result |

**G3 and G4 are non-negotiable.** They are the gates that stop the project from
producing a confident false positive, which is the most likely bad outcome here
— more likely than a true positive.

---

## 6. Honest summary

CAWA as specified in the brief — cross-architecture structural weight
transplantation between arbitrary LLMs without training — is **very unlikely to
work in its most ambitious form**, for reasons that are mathematical rather
than engineering (Prop. 2's corollary, the P2 bottleneck, Prop. 7's tax, and
P5's precondition rarely holding).

But the brief's own §23 anticipates this and asks for the stronger training-free
alternatives, and those are genuinely promising:

- The **measurement** (E0) is valuable regardless of outcome and is cheap.
- The **pruning-recovery** case (E3) satisfies the mandatory assumption exactly,
  has a real baseline, and is more likely than not to work.
- **CAWA-LR** (closed-form low-rank correction) satisfies the letter and spirit
  of "no gradient training" while being the most robust rung on the ladder.

The recommendation is therefore: **build E0 first, gate on it, and treat block
transplantation as the hypothesis being tested rather than the product being
built.** The design in `02` and `03` is complete enough to implement in full,
but implementing it before E0 answers G1 would be spending weeks to learn
something an afternoon can tell us.
