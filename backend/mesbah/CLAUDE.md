# mesbah (the package)

Code that runs outside Django: probes, the CLI, the launcher, the built-in engine and the
trainer, and later the exporters. Django apps import it; it never imports `apps` (ADR-008). It
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
  train/        the training subprocess, `python -m mesbah.train --config <run>/config.json`
    contract.py   the files Django and the trainer exchange: config, events, status
    data.py       example files read and rendered into prompt/completion text
    deltas.py     how large a LoRA delta is, and how far it moved, without forming it
    lora.py       the LoRA/QLoRA trainer: Unsloth, or transformers + PEFT, then TRL
    fake.py       a trainer without torch, for the Django test gate
    __main__.py   reads the config, runs a trainer, exits 0 or 1
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

**`main()`** (`download.py`) — downloads one repository into the HuggingFace cache, skipping
other weight formats when safetensors exist, and prints one JSON line: the snapshot path or an
error code (`gated`, `not_found`, `disk_full`, `network`).

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

**`TrainConfig`** (`train/contract.py`) — what one run trains: the base (`BaseModelRef`, whose
`source` is the local snapshot or the repo id), the `ExampleSource` files, the optional parent
adapter, the paths it reports to, the `Hyperparams` and the GPU indices; `from_json()`/`to_json()` check and write the JSON shape,
`read()`/`write()` the file (written atomically). **`Status`** — how a run ended, with `Failure`,
`Metrics` and `DeltaStats` (`LayerDelta` per module); `read()` loads it, **`write_status()`** replaces it atomically. **`EventWriter`** —
appends one event line per call (`loading`, `data`, `begin`, `log`, `oom_retry`, `saving`,
`done`, `error`), flushed each time; non-finite numbers go out as `null`. **`read_events()`** —
every complete event line. **`ContractError`** — a config or status that does not fit.

**`load_rows()`** (`train/data.py`) — reads example files into `Conversation`s of `Message`s and
`PlainText`s, honouring `max_rows` and counting malformed lines in `Rows.skipped`;
**`parse_row()`** checks one row. **`render()`** — one conversation as a `Pair`: the prompt is the
chat template up to the generation prompt, the completion is the rest of the full rendering
(thinking as `reasoning_content`, `enable_thinking` when the answer has it), or `None` when the
full rendering does not extend the prompt; without a template, plain `User:`/`Assistant:` text.
**`prepare()`** — renders every row (plain text becomes a completion with an empty prompt) into
`Prepared`: the pairs, how many were skipped, their tokens and the first rejection.
**`Tokenizer`** — the part of a tokenizer these functions use.

**`delta_stats()`** (`train/deltas.py`) — per-module and total ‖ΔW‖ of an adapter, its LoRA
parameter count and rank, and its distance from a parent adapter, all from the low-rank factors
(`squared_norm()`, `inner_product()`, `change_between()`). **`read_adapter()`** — every module as a
`LoraModule` (A, B and its scale), **`read_settings()`** the `AdapterSettings` of
`adapter_config.json`, **`lora_pairs()`** the A/B tensors by module, **`module_scale()`** and
**`lora_scale()`** the scale (alpha/r, or alpha/√r with rsLoRA). **`adapter_size_bytes()`** — the
size of a folder.

**`run()`** (`train/lora.py`) — the whole run: reads and renders the examples, plans, loads, grafts
the parent, trains with TRL, retries on CUDA OOM with half the sequence length, saves the adapter,
measures it, and always ends with a written `Status`. **`make_plan()`** — the `Plan`: CUDA or CPU,
how many GPUs, 4-bit or not, Unsloth or transformers, the rank and target modules (grown to cover a
`Parent`, read by **`read_parent()`**, merged by **`merged_targets()`**). **`load_tokenizer()`**,
**`load_model()`** — the tokenizer, then the base with a fresh adapter as `Loaded`
(**`lora_config_for()`** builds the `LoraConfig`, **`compute_dtype()`** picks the dtype).
**`graft()`** — fits a parent's A/B into a rank at least as large so that s·B·A is unchanged;
**`graft_parent()`** does it for every module of a live model. **`build_trainer()`** — the
`SFTTrainer` on prompt/completion data with completion-only loss; **`live_callback()`** writes
`begin`/`log` and stops on the cancel file. **`select_gpus()`** — restricts CUDA to the chosen
cards. **`is_oom()`** — a CUDA OOM anywhere in **`exception_chain()`**; **`describe()`** — an
error as one line; **`free_memory()`** — releases cached GPU memory. **`TrainingFailure`** carries
an error code, **`Cancelled`** a cancel, **`Progress`** what the run has reached.
**`supervise()`** — runs a `Training` and turns however it ends into a written `Status` —
**`guard_load()`** (a failed load step as `load_failed` or `out_of_memory`),
**`check_cancel()`** and **`run_metrics()`**.

**`run()`** (`train/fake.py`) — the same contract without torch: real example counting, falling
loss, the cancel file, a tiny but valid adapter (**`write_adapter()`**, through
**`write_safetensors()`**; **`read_safetensors()`** reads one back) with exact delta stats.
**`knobs()`** reads `MESBAH_FAKE_TRAINER`: `fail`, `oom`, `slow`, comma-separated.

**`main()`** (`train/__main__.py`) — `python -m mesbah.train --config <path> [--fake]`; runs the
LoRA trainer, exits 0 for completed or cancelled and 1 for failed,
turns SIGTERM into a cancel, and still writes a failed status when the config itself cannot be
read.

**`ExportConfig`**, **`ExportStatus`** (`export/contract.py`) — what an export makes (`merged` or
`gguf`, from a base and an optional adapter, with an `out_type`) and how it ended.
**`merge()`** (`export/merge.py`) — loads the base in its own dtype, folds the adapter in with
PEFT and saves sharded safetensors with the tokenizer files. **`converter()`**
(`export/converter.py`) — llama.cpp's `convert_hf_to_gguf.py` and its own `gguf-py` from release
`LLAMA_CPP_TAG`, downloaded once into the tools folder and refused unless every file matches
its pinned sha256. **`main()`**, **`run()`** (`export/__main__.py`) — merges when there is an
adapter, converts to GGUF beside a `Modelfile`, and writes the status (`converter_unavailable`,
`conversion_failed`, `out_of_memory`, `nothing_to_merge`, `failed`).

## The training contract

A run is a folder Django owns. Django writes `config.json`, starts
`python -m mesbah.train --config <run>/config.json` (with `--fake` in the test gate) and only reads
files after that; the trainer never imports Django.

- **`config.json`** — `TrainConfig`. `base.path` is a downloaded snapshot (else `repo_id` at
  `revision` is loaded), `parent_adapter` is the folder of the version being enhanced, `examples`
  are JSONL files, `gpu_indices` are NVML indices and empty means CPU.
- **Example rows** — `{"messages": [{"role", "content", "thinking"?}, …]}`, the last message being
  the assistant reply to learn, or `{"text": …}`. Malformed lines are skipped and counted.
- **`events.jsonl`** — appended, one JSON object per line, each with `ts` and `event`:
  `loading{stage: data|tokenizer|model|parent}`,
  `data{examples, skipped, tokens}`,
  `begin{total_steps}`, `log{step, total_steps, epoch, loss, learning_rate, grad_norm}`,
  `oom_retry{max_seq_len}`, `saving{}`, `done{}`, `error{code, detail}` with code
  `out_of_memory | no_examples | load_failed | failed`.
- **`status.json`** — written once at the end: `status` (`completed | failed | cancelled`),
  `adapter_dir`, `size_bytes`, `delta` (`layers[{name, layer, module,
  norm}]`, `total_norm`, `parameters`, `rank`, `change_from_parent`), `error{code, detail}` and
  `metrics{final_loss, steps, examples, skipped, seconds}`.
- **`cancel`** — Django creates it; the trainer checks it every step, stops, saves nothing and
  writes `cancelled`.
- **`output_dir`** — only the adapter, as PEFT saves it: `adapter_model.safetensors`,
  `adapter_config.json` and PEFT's `README.md`; never the base weights or the tokenizer.

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

**Every version is one adapter measured from the base.** Enhancing grafts the parent's A rows and
B columns (B rescaled by s_parent/s_new, the remaining columns zero) into a rank at least as large,
so training starts exactly at the parent's ΔW and the saved adapter is cumulative, never a chain.

**A CUDA OOM while loading is not retried.** Halving the sequence length only saves activation
memory; a model that does not fit fails at once as `out_of_memory`.

**Unsloth only on one GPU with no rank growth.** Open-source Unsloth is single-GPU, and the HF
path is the one tested with grafting into a larger rank; any Unsloth failure falls back to it.

**GGUF goes through llama.cpp's own converter, pinned.** Only llama.cpp keeps up with every
architecture's tensor names; its release `b9000` is the last with a one-file converter, and its
`gguf-py` travels with it so no other `gguf` package can disagree with it.

**No brotli workaround.** huggingface_hub 2.x downloads through httpx2, whose brotli decoder drains
its output before taking more input, so the 1.x crash cannot happen; the trainer also loads from a
local snapshot.
