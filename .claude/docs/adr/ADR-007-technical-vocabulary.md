# ADR-007: Mesbah names models and a fixed technical vocabulary

**Status:** accepted — 2026-10-18

## Context

`language.md` rule 8 says a model, algorithm or library name never renders to a user, and
that a technical term is replaced by the reader's word or spelled out once. That fits a
product whose users never meet the machinery. Mesbah's users choose a model by its name,
size the run to their GPU, and read a loss curve. Hiding `Qwen/Qwen3-14B` behind "a large
model", or LoRA behind "a small change", leaves them unable to search for it, compare it
or ask about it elsewhere.

## Decision

- **Model, dataset and engine names render exactly as their publishers write them**
  (`Qwen/Qwen3-14B`, `trl-internal-testing/zen`, vLLM, llama.cpp, Ollama), in their own
  direction (`dir="ltr"` on the name element only).
- **A fixed vocabulary stays in English in both languages**, never translated or
  transliterated: LoRA, QLoRA, GPU, VRAM, RAM, CPU, loss, learning rate, token, MoE,
  GGUF, safetensors, API, API key. The list lives in `language.md` under "Technical terms".
  A term outside the list is written in the reader's words.
- **Every listed term on screen has its explanation one action away**, through the shared
  `<app-term>` component, in the reader's language. A term with no glossary entry is a
  finding for `copywriter`.
- Everything else in rule 8 holds: library names (transformers, PEFT, TRL, bitsandbytes)
  and algorithm names stay off screen unless they are on the list.

## Consequences

The Arabic interface carries some Latin words; they sit in their own direction and are
explained in Arabic. `unifier` treats the list as part of the vocabulary table, so a
second spelling of a listed term is a divergence.
