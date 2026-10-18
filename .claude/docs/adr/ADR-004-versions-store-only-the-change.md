# ADR-004: A version stores only the change, measured from the base

**Status:** accepted — 2026-10-18

## Context

Mesbah keeps every customisation of a model as a version a person can return to. Saving a
checkpoint per version would copy the whole model each time — tens of gigabytes for a 14B model —
and the request was for versions that change the weights and biases and keep only that change.

## Decision

- **The root of a fine-tune project is the base model as downloaded.** It stays in the
  HuggingFace cache; nothing is copied.
- **Every other version is one LoRA adapter whose ΔW is measured from the base**, not from its
  parent. Enhancing a version starts a new adapter from the parent's tensors (grafted into a rank
  at least as large, so the starting ΔW is exactly the parent's) and keeps training. The parent
  link records lineage only.
- Biases can be trained too (`bias="lora_only"`) where the model has them; such a version can
  only be exported merged, so it is an Expert option.
- What changed is computed from the low-rank factors alone — ‖BA‖² = tr((BᵀB)(AAᵀ)) per module,
  and the distance from the parent the same way — and stored with the version.
- Activating a version is the rollback. Version numbers are never reused.
- A model trained from scratch has no base, so its root is the one full copy Mesbah writes.

## Consequences

- Any engine loads exactly one adapter for any version; latency does not grow with depth, and
  removing a version in the middle of the tree breaks none of its descendants.
- Storage per version is the adapter (megabytes), the same total as a chain of deltas.
- Every version can be merged into full weights for engines that need them (GGUF, Ollama).
- Two versions trained from different parents cannot be combined by adding their deltas; that
  would be a separate merge feature.
