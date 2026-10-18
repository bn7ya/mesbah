# ADR-005: Every engine is an OpenAI-compatible server; Mesbah ships one

**Status:** accepted — 2026-10-18

## Context

A version has to run somewhere: on Mesbah's own machine for chatting and correcting, and on the
engines people already use — vLLM, llama.cpp, Ollama, any OpenAI-compatible server. Running a
model inside the Django process would put torch and gigabytes of weights in every web worker,
and the web process must boot without the training parts at all.

## Decision

- **Every engine is reached over HTTP with one client**, speaking OpenAI's
  `/v1/chat/completions`, streamed. Thinking is read from `reasoning_content` (or `reasoning`, or
  a `<think>` block in the content) and kept apart from the answer.
- **The built-in engine is `python -m mesbah.runtime`**, a Starlette server in its own process:
  one base model in memory, each version a named PEFT adapter selected per request under a lock,
  `base` served with the adapters off. `/admin/load`, `/admin/unload` and `/admin/status` let
  Django decide what is loaded. It listens on 127.0.0.1 (pip) or the compose network (Docker)
  and answers only to a token.
- **`apps.serving` owns engines.** An `Engine` row per server; the built-in one is created by a
  migration and is the default. `DeploymentService.target()` loads what a conversation needs and
  returns the address and model name to stream from; `release()` frees the GPU for training.
- `mesbah start` runs the engine when the training parts are installed and tells the person
  how to install them when not. Docker runs it as the `runtime` service: `--profile engine` on
  the CPU, `compose.gpu.yaml` on the GPUs.

## Consequences

- External engines differ only in how a version gets onto them (vLLM's runtime LoRA loading,
  llama.cpp's `--lora`, Ollama's merged GGUF), which is `DeploymentService`'s job, not the chat's.
- One generation at a time on the built-in engine: PEFT's active adapter is global state.
- The engine can stop or crash without taking the web app with it; the Engines page and the chat
  say it is not running.
