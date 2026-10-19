# Changelog

Every release of Mesbah, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). While the version starts with 0, a
minor release may change what an earlier one promised, and says so under **Contracts**.

## [Unreleased]

The first release.

### Added

- **Models.** Search HuggingFace, an exact `owner/name` included. See what a model is and
  whether it fits this machine's GPU, memory and disk, then download it.
- **Projects.** Each project is one model being customized, with Overview, Chat, Training and
  Versions tabs.
- **Chat.**
  - Stream replies from any version.
  - Edit a reply in place, and edit its thinking separately.
  - Approve replies as training examples.
- **Datasets.**
  - Import a HuggingFace dataset: messages, ShareGPT, instruction, prompt and completion, or
    plain text. Thinking columns become thinking.
  - Or upload a file.
- **Training.** Train a new version from approved replies and library datasets, and watch it
  live.
- **Versions.**
  - Every version is one LoRA delta from the base.
  - Roll back by activating any version, and see which layers changed.
  - Export a LoRA adapter, merged weights or GGUF.
- **Architect.** Design a dense, mixture-of-experts or encoder-decoder model, see its size and
  memory, and train it from nothing.
- **Engines.**
  - The built-in engine, vLLM, Ollama, llama.cpp or any OpenAI-compatible server.
  - API keys.
  - OpenAI- and Ollama-compatible APIs at `/v1` and `/ollama`.
- **System and Members.**
  - The machine's hardware and installed parts, and the HuggingFace token.
  - Roles: viewer, reviewer, trainer and administrator.
- **Two ways to run.**
  - `pip install mesbah && mesbah start`, with an embedded PostgreSQL.
  - Docker Compose, with GPU and engine profiles.
