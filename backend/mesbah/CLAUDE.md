# mesbah (the package)

Code that runs outside Django: probes, and later the CLI, the launcher, the built-in engine,
the trainers and the exporters. Django apps import it; it never imports `apps` (ADR-008). It
is application code, so every rule holds: typed, no docstrings, tests beside it.

## What lives here

```
mesbah/
  paths.py      where Mesbah keeps its data
  hardware.py   GPUs, RAM and CPU of this machine
  parts.py      which optional packages are installed, read from metadata
  tests/
```

## Classes and methods

**`data_dir()`** (`paths.py`) — the data folder: `MESBAH_DATA_DIR`, or the user data folder
of the platform. **`ensure()`** — creates a folder and returns it.

**`Gpu`**, **`Machine`** (`hardware.py`) — what was found. **`gpus()`** — every NVIDIA GPU and
the driver version, from NVML, then `nvidia-smi`, else none; cached for the process.
**`ram_bytes()`** — total memory, with a Windows fallback. **`machine()`** — everything at
once. **`forget()`** — drops the cached GPU probe.

**`Part`**, **`parts()`** (`parts.py`) — each optional package, what it enables and its
installed version, read from package metadata without importing it. `Part.cuda` says whether
the installed torch is a CUDA build, when its version says so.

## Decisions worth not re-litigating

**No torch import to find a GPU.** Importing torch takes seconds and gigabytes; NVML answers
in milliseconds and works without the training parts.
