# Model Selection — base model for Arabic long-context QLoRA on a 16 GB RTX 5080

> **Note:** the app no longer hardcodes this list. The new-project picker and
> the models page list models **live from the HuggingFace API** (featured +
> search). This document remains as *guidance* for choosing a base model; the
> only remaining default is the env-overridable `MISBAH_DEFAULT_BASE_MODEL`
> fallback (`Qwen/Qwen3-14B`).

> Decision: **Qwen/Qwen3-14B** is the default base model. **Qwen/Qwen3-8B** is the
> safest fallback. Researched against the constraint "latest Qwen or DeepSeek,
> excellent Arabic, long context, QLoRA on 16 GB" (mid-2026).

## TL;DR recommendation

| Pick | HF repo id | Why |
|------|-----------|-----|
| **Primary** | `Qwen/Qwen3-14B` | Newest Qwen that is *actually* 4-bit QLoRA-trainable on 16 GB. Apache-2.0, 119 languages incl. Arabic, native 32K → 131K via YaRN. Unsloth confirms it QLoRA-fits a 16 GB GPU. |
| **Fallback** | `Qwen/Qwen3-8B` | ~2–3× more trainable context (~8–16K vs ~4–8K) and faster iteration; same Arabic coverage. Use if 14B is tight. |
| **DeepSeek option** | `deepseek-ai/DeepSeek-R1-0528-Qwen3-8B` | Best DeepSeek-branded choice (built on Qwen3-8B-Base, so inherits Arabic). MIT. Always-on reasoning — pick only for chain-of-thought tasks. |
| **Long-context specialist** | `Qwen/Qwen2.5-14B-Instruct-1M` | Only if you need genuine >128K. Weaker Arabic (29 langs); true 1M serving needs huge VRAM. |
| **Arabic specialist (relaxes the constraint)** | `ALLaM-AI/ALLaM-7B-Instruct-preview`, `Navid-AI/Yehia-7B-preview` | Materially better native Arabic (ArabicMMLU ~67.8, AraGen-leading) but **only 4K context** and **not** Qwen/DeepSeek-derived. |

For 4-bit *fast load*, Unsloth pre-quantized repos exist:
`unsloth/Qwen3-14B-unsloth-bnb-4bit`, `unsloth/Qwen3-8B-unsloth-bnb-4bit`.

## Why not the newest Qwen (3.5 / 3.6)?

Qwen3.5-9B / Qwen3.6 have **better Arabic on paper** (201 languages) and longer
native context, **but Unsloth explicitly does NOT recommend 4-bit QLoRA for any
Qwen3.5/3.6 model** (high quantization error + bitsandbytes limits); bf16 LoRA
needs ~22 GB > 16 GB. They are 24 GB+ targets. **Qwen3-14B is the newest Qwen
that QLoRA-trains on a 5080.**

## Arabic quality, honestly

There is **no published per-checkpoint Arabic benchmark** for Qwen3-14B; its
Arabic is credible but *qualitative*. Dedicated specialists (ALLaM, Fanar,
Jais-2) still beat vanilla Qwen3 on Arabic cultural alignment, dialects and MSA
fluency. **Your Arabic QLoRA fine-tune is exactly what closes that gap** — budget
good Arabic instruction data (MSA + target dialects). This studio's correction
loop is the mechanism for that.

## Memory budget (4-bit NF4, batch=1, grad-checkpointing ON, bf16)

| Item | Qwen3-8B | Qwen3-14B |
|------|---------:|----------:|
| Frozen base (NF4 + double-quant) | ~5.0 GB | ~8.0 GB |
| LoRA adapters + grads | ~0.4 GB | ~0.4 GB |
| Optimizer (8-bit, adapters only) | ~0.2 GB | ~0.2 GB |
| CUDA ctx + kernels + frag | ~1.5 GB | ~1.5 GB |
| **Fixed subtotal** | **~7.1 GB** | **~10.1 GB** |
| **Activation budget** | **~8.9 GB** | **~5.9 GB** |
| Max trainable ctx (Unsloth) | **~22–30K** | **~8–14K** |
| Recommended seq_len | 8,192 | 4,096 |
| Optimizer | adamw_8bit | paged_adamw_8bit |

Set max trainable context ~10 % below the theoretical number to dodge
fragmentation OOM.

## Default QLoRA hyper-parameters (see `backend/app/features/projects/service.py`)

- `load_in_4bit=True`, `nf4`, double-quant, compute dtype `bfloat16`,
  `attn_implementation="sdpa"` (no flash-attn on Blackwell).
- LoRA: `r=16` (14B) / `32` (8B), `alpha = r` or `2r`, `dropout=0.0`,
  `target_modules` = all linear (`q,k,v,o,gate,up,down`).
- `use_gradient_checkpointing="unsloth"` for long context.
- `optim=paged_adamw_8bit`, `lr=2e-4`, cosine, `warmup_ratio=0.03`, `bf16=True`.
- Effective batch via `grad_accum_steps` (default 16).

## Long-context strategy

Train short, serve long. Qwen3's native window is 32,768.
1. If your data fits 32K → **don't** add YaRN; train at the largest seq_len VRAM allows.
2. To serve 64K–128K, add `rope_scaling {type: yarn, factor: target/32768}` and
   fine-tune on short sequences (YaRN extrapolates with only a few hundred steps).
3. Validate perplexity/retrieval at the **real** target length — RoPE interpolation
   on 4-bit weights has known stability issues at very long context.

## Key risks (carried into the build)

- bitsandbytes on cu130 needs the CUDA-13 runtime libs (`nvidia-cuda-runtime-cu13`,
  `nvidia-cuda-nvrtc-cu13`, `nvidia-nvjitlink-cu13`) or it throws
  `Missing dependency: libnvJitLink.so.13`. Verify with `python -m bitsandbytes`.
- flash-attention has **no** Blackwell sm_120 build — use `sdpa` + Unsloth kernels.
- transformers is on the 5.x line; 5.5.x is the battle-tested Blackwell-QLoRA series.
