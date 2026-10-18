# mesbah (the package)

Code that runs outside Django: probes, and later the CLI, the launcher, the built-in engine,
the trainers and the exporters. Django apps import it; it never imports `apps` (ADR-008). It
is application code, so every rule holds: typed, no docstrings, tests beside it.

## What lives here

```
mesbah/
  cli.py        the `mesbah` command: start, doctor, manage
  launcher.py   starts and stops the database, the web server and the worker
  server.py     where the Django tree and the built Angular app are
  database.py   a PostgreSQL URL as Django settings
  paths.py      where Mesbah keeps its data
  hardware.py   GPUs, RAM and CPU of this machine
  sizing.py     what a model's config says it is, and whether it fits in memory
  download.py   `python -m mesbah.download`: one HuggingFace snapshot, as a subprocess
  parts.py      which optional packages are installed, read from metadata
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
web server and the worker, waits for `/api/health/`, prints the address and the setup code, and
supervises until Ctrl+C or SIGTERM; `prepare()` builds the children's environment (database,
secret key, origins, the built app); `start_database()` starts the embedded PostgreSQL;
`manage()` runs one Django command; `stop()` stops the children, then the database it owns.
**`Options`** — host, port, data folder, an optional database URL, whether to open a browser.
**`secret_key()`** — the Django secret key, made once and kept owner-only in the data folder.

**`server_root()`**, **`spa_dir()`**, **`python_path()`** (`server.py`) — the Django tree
(bundled `_server/`, or the checkout's `backend/`), the built Angular app if any, and the
`PYTHONPATH` children need. **`django_database()`** (`database.py`) — Django's `DATABASES` entry
for a `postgres://` URL, socket hosts included, pooled.

## Decisions worth not re-litigating

**Children are processes, not threads.** uvicorn and Celery each want the main thread and their
own signal handling; the launcher only starts, watches and stops them.

**The launcher stops the database it started even when other handles remain.** A process killed
without cleanup leaves its handle behind, and the embedded server would otherwise run forever.

**No torch import to find a GPU.** Importing torch takes seconds and gigabytes; NVML answers
in milliseconds and works without the training parts.
