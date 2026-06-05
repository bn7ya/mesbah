# Hardware & Software Stack

## The machine

| | |
|---|---|
| GPU | NVIDIA GeForce **RTX 5080**, 16 GB GDDR7, **Blackwell sm_120** |
| Driver / CUDA | 595.71.05 / CUDA 13.2 runtime |
| CPU | Intel Core i9 (14th gen) |
| RAM | 128 GB DDR5 |
| OS | Linux (CachyOS), Python 3.13 (miniconda base) |
| PyTorch | **2.11.0+cu130** (pre-installed, CUDA available) ✅ |

16 GB VRAM is the binding constraint — it drives the model choice (8–14B 4-bit)
and the QLoRA memory budget (see `MODEL_SELECTION.md`).

## The Blackwell QLoRA stack (the tricky part)

Blackwell (sm_120) + CUDA 13 is new enough that the usual stack needs care:

```bash
# torch is already installed — do NOT reinstall:  torch==2.11.0+cu130
cd backend
pip install -r requirements-ml.txt
python -m bitsandbytes          # MUST print a working report
```

`requirements-ml.txt` pins, with rationale:

- `nvidia-cuda-runtime-cu13`, `nvidia-cuda-nvrtc-cu13`, `nvidia-nvjitlink-cu13`
  — **required** so bitsandbytes finds CUDA-13 runtime libs on a cu130 torch.
  Without them: `Missing dependency: libnvJitLink.so.13`.
- `bitsandbytes>=0.49.2` — single fat wheel; sm_120 + CUDA 13 supported.
- `transformers>=5.5.0` — 5.5.x is the battle-tested Blackwell-QLoRA series.
- `peft>=0.19.1`, `trl>=0.29.1`, `accelerate>=1.13.0`, `datasets>=4.8.5`,
  `triton>=3.3.1` (sm_120; usually bundled with torch 2.11).
- `unsloth` + `unsloth_zoo` — preferred; ~2× faster, ~50–70 % less VRAM, ~4×
  longer trainable context than plain trl. Officially supports RTX 50-series.

### Do NOT install flash-attention

FA2 is Ampere/Ada/Hopper only; FA3 refuses Blackwell. The code uses
`attn_implementation="sdpa"` and Unsloth's Triton kernels instead.

## Escape hatches

- bnb errors after an upgrade → clear `/tmp/unsloth_compiled_cache/`.
- `CUBLAS_STATUS_EXECUTION_FAILED` → `TORCHDYNAMO_DISABLE=1 UNSLOTH_COMPILE_DISABLE=1`.
- Alternative to the `nvidia-*-cu13` wheels:
  `export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/cuda-13.2/lib64`.

## Inference vs training share one GPU

On 16 GB you cannot comfortably hold a chat model **and** train at once. The
training manager calls `inference_engine.unload()` before launching a run, giving
the fine-tune the whole card. After a run completes, the next chat reloads.
