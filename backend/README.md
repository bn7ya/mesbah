# مصباح · Mesbah

A studio for customizing language models, for one person or a whole team. Pick any model on
HuggingFace, chat with it, correct its replies and its thinking in place, add HuggingFace
datasets, and train. Every run adds a **version** that stores only the change to the model's
weights. Versions run on the built-in engine, vLLM, llama.cpp or Ollama, export to their
formats, and are served over OpenAI- and Ollama-compatible APIs. The interface is Arabic first,
with English one switch away.

## Install and run

```bash
pip install mesbah
mesbah start
```

`mesbah start` brings up its own PostgreSQL in your user data folder, opens the browser, and
prints a one-time setup code that creates the owner account. Press Ctrl+C to stop.

Training and the built-in engine need the training parts. With an NVIDIA GPU, install PyTorch
for CUDA first, then the extra:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu130
pip install "mesbah[train]"
```

`mesbah doctor` checks the machine and says what is missing.

## Options

| Command | What it does |
|---|---|
| `mesbah start --port 8077 --host 127.0.0.1` | where to listen |
| `mesbah start --database-url postgresql://…` | use your own PostgreSQL |
| `mesbah --data-dir /path start` | keep data somewhere else (or set `MESBAH_DATA_DIR`) |
| `mesbah manage <command>` | run a Django management command, e.g. `setup_code` or `dbs backup` |

Docker, development and the full documentation: <https://github.com/bn7ya/mesbah>.
