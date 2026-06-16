"""Pure-Python architecture math — parameter counting + memory feasibility.

No torch / transformers import here: this runs at the API layer (which must boot
without the ML stack). The trainer subprocess (``scripts/train_scratch.py``) is
the only place that actually instantiates a model from this spec.

Everything below is an **estimate**. The point is to let the user see roughly how
big a model they are designing and whether it can possibly train on the box —
not to be exact to the byte.
"""
from __future__ import annotations

from ...core.config import settings
from .schemas import (ArchitectureSpec, FeasibilityEstimate, MemoryVerdict,
                       ParamBreakdown, SolveHiddenRequest)

_BYTES_BF16 = 2


def _human(n: int) -> str:
    for unit, scale in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if n >= scale:
            return f"{n / scale:.2f}{unit}"
    return str(n)


def _intermediate(spec: ArchitectureSpec) -> int:
    if spec.intermediate_size:
        return spec.intermediate_size
    # SwiGLU MLPs conventionally use ~8/3·hidden, rounded; ~4·hidden is a fine
    # default for the estimate when the user leaves it blank.
    return 4 * spec.hidden_size


def _moe_intermediate(spec: ArchitectureSpec) -> int:
    return spec.moe_intermediate_size or _intermediate(spec)


def _kv_heads(spec: ArchitectureSpec) -> int:
    return spec.num_key_value_heads or spec.num_attention_heads


def count_params(spec: ArchitectureSpec) -> ParamBreakdown:
    h = spec.hidden_size
    head_dim = max(1, h // spec.num_attention_heads)
    kv = _kv_heads(spec)

    # ── embeddings (input + output head; shared if tied) ──
    embed = spec.vocab_size * h
    embeddings = embed if spec.tie_word_embeddings else embed * 2

    # ── per-layer attention: q/o are hidden×hidden; k/v project to kv heads ──
    q = h * (spec.num_attention_heads * head_dim)
    o = (spec.num_attention_heads * head_dim) * h
    k = h * (kv * head_dim)
    v = h * (kv * head_dim)
    attn_per_layer = q + k + v + o

    # ── per-layer MLP ──
    inter = _intermediate(spec)
    if spec.is_moe:
        expert = 3 * h * _moe_intermediate(spec)          # gate+up+down per expert
        router = h * spec.num_experts
        mlp_total_per_layer = spec.num_experts * expert + router
        mlp_active_per_layer = spec.num_experts_per_tok * expert + router
    else:
        dense = 3 * h * inter
        mlp_total_per_layer = dense
        mlp_active_per_layer = dense

    L = spec.num_hidden_layers
    attention = attn_per_layer * L
    mlp = mlp_total_per_layer * L
    mlp_active = mlp_active_per_layer * L
    other = (2 * h) * L + h                                # layernorms + final norm

    total = embeddings + attention + mlp + other
    active = embeddings + attention + mlp_active + other
    return ParamBreakdown(
        embeddings=embeddings, attention=attention, mlp=mlp, other=other,
        total_params=total, active_params=active,
        total_params_human=_human(total), active_params_human=_human(active),
    )


def estimate_memory(spec: ArchitectureSpec, params: ParamBreakdown,
                    batch_size: int = 1) -> MemoryVerdict:
    p = params.total_params
    weights = p * _BYTES_BF16
    gradients = p * _BYTES_BF16                            # full training: all params trainable
    optimizer = p * 2                                     # paged 8-bit AdamW: m+v ≈ 2 bytes/param
    # Activations (gradient-checkpointed): dominated by one resident layer's
    # forward over the sequence. Rough: batch·seq·hidden·(a few tensors)·bytes.
    seq = spec.max_position_embeddings
    activation = batch_size * seq * spec.hidden_size * 18 * _BYTES_BF16

    gb = 1024 ** 3
    weights_gb = weights / gb
    grad_gb = gradients / gb
    opt_gb = optimizer / gb
    act_gb = activation / gb
    total_gb = weights_gb + grad_gb + opt_gb + act_gb

    vram = settings.gpu_vram_gb
    # Resident-on-GPU need if NOT paging is roughly weights+grads+activations
    # (optimizer is paged to CPU). Fits only if that comfortably clears VRAM.
    resident = weights_gb + grad_gb + act_gb
    if resident <= vram * 0.8:
        verdict = "fits"
    elif total_gb <= vram * 40:                           # plausibly pageable to CPU/disk
        verdict = "needs_paging"
    else:
        verdict = "extreme"
    return MemoryVerdict(
        weights_gb=round(weights_gb, 2), gradients_gb=round(grad_gb, 2),
        optimizer_gb=round(opt_gb, 2), activation_gb=round(act_gb, 2),
        total_gb=round(total_gb, 2), gpu_vram_gb=vram, verdict=verdict,
        paging_required=verdict != "fits",
    )


def estimate(spec: ArchitectureSpec) -> FeasibilityEstimate:
    params = count_params(spec)
    mem = estimate_memory(spec, params)
    warnings: list[str] = []

    if spec.num_attention_heads and spec.hidden_size % spec.num_attention_heads:
        warnings.append(
            f"hidden_size ({spec.hidden_size}) is not divisible by "
            f"num_attention_heads ({spec.num_attention_heads}); the trainer will reject this."
        )
    if _kv_heads(spec) and spec.num_attention_heads % _kv_heads(spec):
        warnings.append(
            f"num_attention_heads ({spec.num_attention_heads}) must be a multiple of "
            f"num_key_value_heads ({_kv_heads(spec)})."
        )
    if spec.is_moe and spec.num_experts_per_tok > spec.num_experts:
        warnings.append("num_experts_per_tok cannot exceed num_experts.")

    if mem.verdict == "needs_paging":
        warnings.append(
            "This model exceeds VRAM and will require paged training (weights/optimizer "
            "streamed to CPU/disk). Steps will be much slower."
        )
    if mem.verdict == "extreme" or params.total_params >= 1_000_000_000:
        warnings.append(
            "⚠ Training a model this size FROM SCRATCH on a single GPU is not feasible to "
            "converge: it needs many billions of tokens and very long wall-clock time. "
            "Paging fits it in memory but cannot fix the compute/data requirement. "
            "Expect an experimental, undertrained model."
        )
    if spec.max_position_embeddings > 8192:
        warnings.append(
            "Large context windows multiply activation memory and slow each step; "
            "consider training at a smaller context first."
        )

    suggested_budget = max(1, settings.gpu_vram_gb - 1)
    return FeasibilityEstimate(
        spec=spec, params=params, memory=mem, warnings=warnings,
        suggested_gpu_budget_gb=suggested_budget,
    )


def solve_hidden(req: SolveHiddenRequest) -> dict:
    """Binary-search a hidden_size whose total params land near the target.

    Heads/vocab are held fixed; we keep hidden divisible by a reasonable head
    count so the result is trainable. Returns the spec + its estimate.
    """
    lo, hi = 8, 32768

    def params_for(h: int) -> int:
        heads = max(1, h // 64)                            # 64-dim heads
        spec = ArchitectureSpec(
            family=req.family, num_hidden_layers=req.num_hidden_layers,
            hidden_size=h, num_attention_heads=heads, vocab_size=req.vocab_size,
            num_experts=req.num_experts,
        )
        return count_params(spec).total_params

    best = lo
    while lo <= hi:
        mid = ((lo + hi) // 2) // 64 * 64 or 64
        if params_for(mid) < req.target_params:
            best = mid
            lo = mid + 64
        else:
            hi = mid - 64
    heads = max(1, best // 64)
    spec = ArchitectureSpec(
        family=req.family, num_hidden_layers=req.num_hidden_layers,
        hidden_size=best, num_attention_heads=heads, vocab_size=req.vocab_size,
        num_experts=req.num_experts,
    )
    return {"suggested_hidden_size": best, "estimate": estimate(spec)}


def build_config_dict(spec: ArchitectureSpec) -> dict:
    """Assemble ``transformers`` config kwargs for the chosen family.

    Consumed by ``scripts/train_scratch.py`` (which turns it into an AutoConfig
    and random-inits the model). Kept here so the spec→config mapping has one
    home, but note: this returns a plain dict (no torch) so it stays importable
    at the API layer.
    """
    h = spec.hidden_size
    cfg = {
        "model_type": spec.family if spec.family != "qwen3_moe" else "qwen3_moe",
        "hidden_size": h,
        "num_hidden_layers": spec.num_hidden_layers,
        "num_attention_heads": spec.num_attention_heads,
        "num_key_value_heads": _kv_heads(spec),
        "intermediate_size": _intermediate(spec),
        "vocab_size": spec.vocab_size,
        "max_position_embeddings": spec.max_position_embeddings,
        "tie_word_embeddings": spec.tie_word_embeddings,
    }
    if spec.is_moe:
        cfg.update({
            "num_experts": spec.num_experts,
            "num_local_experts": spec.num_experts,          # mixtral naming
            "num_experts_per_tok": spec.num_experts_per_tok,
            "moe_intermediate_size": _moe_intermediate(spec),
        })
    return cfg
