# mesbah (the package)

Code that runs outside Django: probes, the CLI, the launcher, the built-in engine and the
exporters, and later the trainers. Django apps import it; it never imports `apps` (ADR-008). It
is application code, so every rule holds: typed, no docstrings, tests beside it.

## What lives here

```
mesbah/
  cli.py        the `mesbah` command: start, doctor, manage
  launcher.py   starts and stops the database, the web server, the workers and the engine
  server.py     where the Django tree and the built Angular app are
  database.py   a PostgreSQL URL as Django settings
  paths.py      where Mesbah keeps its data
  hardware.py   GPUs, RAM and CPU of this machine
  sizing.py     what a model's config says it is, and whether it fits in memory
  download.py   `python -m mesbah.download`: one HuggingFace snapshot, as a subprocess
  parts.py      which optional packages are installed, read from metadata
  think.py      thinking chains: split from the answer, joined back, split while streaming
  runtime/      the built-in engine: `python -m mesbah.runtime`, an OpenAI-compatible server
    engine.py     one base model in memory, its versions as adapters, generation
    app.py        the HTTP API over the engine (Starlette)
    specs.py      the request bodies, parsed and checked
    errors.py     each failure with its error code and HTTP status
    __main__.py   the command
  export/       `python -m mesbah.export --config <path>`: merged weights and GGUF files
    contract.py   the config Django writes and the status the exporter leaves
    merge.py      a version's change folded into its base
    converter.py  llama.cpp's converter at a pinned release, fetched and checked by digest
    __main__.py   merges, converts, writes the Modelfile and the status
  _server/      only in the wheel: apps/ and config/
  _spa/         only in the wheel: the built Angular app
  tests/
```

## Classes and methods

**`data_dir()`** (`paths.py`) — the data folder: `MESBAH_DATA_DIR`, or the user data folder
of the platform. **`ensure()`** — creates a folder and returns it.

**`Gpu`**, **`Machine`** (`hardware.py`) — what was found. **`gpus()`** — every NVIDIA GPU and
the driver version, from NVML, then `nvidia-smi`, else none; cached for the process.
**`ram_bytes()`** — total memory, with a Windows fallback. **`machine()`** — everything at
once. **`forget()`** — drops the cached GPU probe.

**`architecture()`** (`sizing.py`) — a model's `config.json` as plain fields (family, layers,
hidden size, heads, context, experts), reading multimodal configs' `text_config`.
**`active_parameters()`** — the parameters a mixture of experts uses per token.
**`chat_bytes()`**, **`qlora_bytes()`**, **`fit()`** — memory estimates for chatting in 4-bit or
half precision and for QLoRA training, and the verdict against the VRAM available.
**`supports_thinking()`** — whether a chat template knows a thinking chain.

**`Part`**, **`parts()`** (`parts.py`) — each optional package, what it enables and its
installed version, read from package metadata without importing it. `Part.cuda` says whether
the installed torch is a CUDA build, when its version says so.

**`main()`** (`cli.py`) — parses `mesbah [--data-dir] start|doctor|manage`; a bare `mesbah` is
`start`. **`start()`** runs the launcher; **`doctor()`** prints the machine, the installed parts
(and the CUDA install command when a GPU sits beside a CPU-only torch) and whether the port is
free; **`manage()`** runs a Django command against Mesbah's database.

**`Launcher`** (`launcher.py`) — `run()` prepares, migrates, collects static files, starts the
web server, the worker, the heavy worker (one job at a time: training, merging, converting) and,
when the training parts are installed, the built-in engine; waits for `/api/health/`, prints
the address, the engine and the setup code, and supervises until Ctrl+C or SIGTERM (the engine
may stop without taking the rest down); `prepare()` builds the children's environment
(database, secret key, origins, the built app, the engine's address and a fresh token);
`start_database()` starts the embedded PostgreSQL; `manage()` runs one Django command; `stop()`
stops the children, then the database it owns. **`engine_installed()`** — whether the parts the
engine needs are there. **`Options`** — host, port, data folder, an optional database URL,
whether to open a browser, the engine's port.
**`secret_key()`** — the Django secret key, made once and kept owner-only in the data folder.

**`server_root()`**, **`spa_dir()`**, **`python_path()`** (`server.py`) — the Django tree
(bundled `_server/`, or the checkout's `backend/`), the built Angular app if any, and the
`PYTHONPATH` children need. **`django_database()`** (`database.py`) — Django's `DATABASES` entry
for a `postgres://` URL, socket hosts included, pooled.

**`split_thinking()`** (`think.py`) — a model's text as its thinking chain and its answer: a
closed `<think>` block, an unclosed one (all thinking), none (all answer), or a close with no
open, which a template that opened the block in the prompt leaves; `starts_inside` says so up
front. **`join_thinking()`** — the two back in the form models write them.
**`ends_inside()`** — whether a rendered prompt leaves a block open. **`ThinkingStream`** — the
same split chunk by chunk: `feed()` returns the pieces it is sure of and holds back what may be
the start of a tag, `close()` flushes the rest; the pieces join to what `split_thinking()` gives.

**`Engine`** (`runtime/engine.py`) — one base model and its versions as named LoRA adapters.
`load()` loads a base, or only adds and replaces adapters when that base is already loaded;
`unload()` stops a running generation and frees the memory; `models()` names `base` and each
adapter; `status()` describes what is loaded; `generate()` checks the model name and returns a
`Generation`. **`Generation`** — one reply, an iterator of text pieces: `begin()` takes the
engine, renders the prompt and starts `generate` on a thread, `close()` stops it and gives the
engine back; then it carries the token counts, the finish reason, and whether the prompt
opened a thinking block. **`Resident`** — what is loaded and how; `render()` applies the chat
template with `enable_thinking` where the template takes it. **`placement()`** — where a base
goes: one GPU whole, several sharing it by `max_memory`, else the CPU in float32.
**`plain_prompt()`** — `User:`/`Assistant:` lines, for a model with no chat template and for an
encoder-decoder. **`sampling()`** — temperature and top_p as `generate` options; 0 or less is
greedy. **`StopWhenSet`** — a stopping criterion that ends generation once an event is set.

**`create_app()`** (`runtime/app.py`) — the Starlette app: `/health` (public), OpenAI's
`/v1/models` and `/v1/chat/completions` (streamed as server-sent events whose deltas are
`reasoning_content` or `content`), and `/admin/load`, `/admin/unload`, `/admin/status`.
**`Api`** — the handlers; engine calls run on worker threads, and a client that leaves stops its
generation. **`RequireToken`** — the bearer token on everything but `/health`, when one is set.
**`Reply`** — the id and time one response's chunks share.

**`LoadSpec`**, **`AdapterSpec`**, **`ChatRequest`**, **`ChatMessage`** (`runtime/specs.py`) —
the bodies the runtime takes; each `from_json()` checks one and raises `InvalidRequest`.
**`EngineError`** (`runtime/errors.py`) — a failure's OpenAI error `code` and HTTP status:
`InvalidRequest` 400, `UnknownModel` 404, `NotLoaded` 409, `LoadFailed` and
`GenerationFailed` 500, `MissingParts` 503.

**`main()`** (`runtime/__main__.py`) — `python -m mesbah.runtime [--host] [--port]` serves a
fresh engine with uvicorn, behind the token in `MESBAH_RUNTIME_TOKEN`.

**`ExportConfig`**, **`ExportStatus`** (`export/contract.py`) — what an export makes (`merged` or
`gguf`, from a base and an optional adapter, with an `out_type`) and how it ended.
**`merge()`** (`export/merge.py`) — loads the base in its own dtype, folds the adapter in with
PEFT and saves sharded safetensors with the tokenizer files. **`converter()`**
(`export/converter.py`) — llama.cpp's `convert_hf_to_gguf.py` and its own `gguf-py` from release
`LLAMA_CPP_TAG`, downloaded once into the tools folder and refused unless every file matches
its pinned sha256. **`main()`**, **`run()`** (`export/__main__.py`) — merges when there is an
adapter, converts to GGUF beside a `Modelfile`, and writes the status (`converter_unavailable`,
`conversion_failed`, `out_of_memory`, `nothing_to_merge`, `failed`).

## Decisions worth not re-litigating

**Children are processes, not threads.** uvicorn and Celery each want the main thread and their
own signal handling; the launcher only starts, watches and stops them.

**The launcher stops the database it started even when other handles remain.** A process killed
without cleanup leaves its handle behind, and the embedded server would otherwise run forever.

**No torch import to find a GPU.** Importing torch takes seconds and gigabytes; NVML answers
in milliseconds and works without the training parts.

**The engine holds one base model; a version is an adapter on it.** Every version is a LoRA
delta from the base, so switching versions selects an adapter instead of loading a model, and
`base` is the same model with its adapters switched off.

**One generation at a time.** PEFT's active adapter is global state on the model, so the
engine's lock is held from selecting the adapter until the generation ends; a request waits for
the one before it. Training calls `unload()`, which interrupts it, or stops the process.

**The runtime splits the thinking, into OpenAI's `reasoning_content`.** Django and any OpenAI
client then read one shape from every engine, as vLLM gives it. The runtime imports the
training parts only to load a model, so Django can import `think` and the specs freely.

**GGUF goes through llama.cpp's own converter, pinned.** Only llama.cpp keeps up with every
architecture's tensor names; its release `b9000` is the last with a one-file converter, and its
`gguf-py` travels with it so no other `gguf` package can disagree with it.
