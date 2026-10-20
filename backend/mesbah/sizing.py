from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mesbah import hardware

type Verdict = Literal["fits", "tight", "too_large", "cpu_only", "unknown"]

GIB: int = 1024**3
FOUR_BIT_BYTES_PER_PARAMETER: float = 0.56
HALF_BYTES_PER_PARAMETER: float = 2.0
RUNTIME_OVERHEAD_BYTES: int = int(1.2 * GIB)
QLORA_FIXED_BYTES: int = 4 * GIB
QLORA_BYTES_PER_PARAMETER: float = 0.62
HEADROOM: float = 1.3

ENCODER_DECODER_TYPES: frozenset[str] = frozenset(
    {"t5", "mt5", "umt5", "bart", "mbart", "pegasus", "switch_transformers", "marian", "longt5"}
)
EXPERT_KEYS: tuple[str, ...] = ("num_experts", "num_local_experts", "n_routed_experts")
EXPERTS_PER_TOKEN_KEYS: tuple[str, ...] = ("num_experts_per_tok", "moe_topk", "top_k")
CONTEXT_KEYS: tuple[str, ...] = ("max_position_embeddings", "n_positions", "max_sequence_length")


@dataclass(frozen=True)
class Architecture:
    family: Literal["dense_decoder", "moe_decoder", "encoder_decoder", "other"]
    model_type: str
    layers: int | None
    hidden_size: int | None
    heads: int | None
    kv_heads: int | None
    vocab_size: int | None
    context_length: int | None
    experts: int | None
    experts_per_token: int | None
    expert_size: int | None


@dataclass(frozen=True)
class Fit:
    verdict: Verdict
    required_bytes: int | None
    available_bytes: int


def _int(config: dict[str, object], *keys: str) -> int | None:
    for key in keys:
        value: object = config.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def architecture(config: dict[str, object]) -> Architecture:
    text: object = config.get("text_config")
    flat: dict[str, object] = {**config, **text} if isinstance(text, dict) else config
    model_type: str = str(flat.get("model_type") or "")
    experts: int | None = _int(flat, *EXPERT_KEYS)
    architectures: object = flat.get("architectures")
    names: list[str] = (
        [str(name) for name in architectures] if isinstance(architectures, list) else []
    )
    family: Literal["dense_decoder", "moe_decoder", "encoder_decoder", "other"]
    if model_type in ENCODER_DECODER_TYPES or flat.get("is_encoder_decoder") is True:
        family = "encoder_decoder"
    elif experts:
        family = "moe_decoder"
    elif any(name.endswith("ForCausalLM") for name in names) or flat.get("num_hidden_layers"):
        family = "dense_decoder"
    else:
        family = "other"
    return Architecture(
        family=family,
        model_type=model_type,
        layers=_int(flat, "num_hidden_layers", "num_layers", "n_layer"),
        hidden_size=_int(flat, "hidden_size", "d_model", "n_embd"),
        heads=_int(flat, "num_attention_heads", "num_heads", "n_head"),
        kv_heads=_int(flat, "num_key_value_heads"),
        vocab_size=_int(flat, "vocab_size"),
        context_length=_int(flat, *CONTEXT_KEYS),
        experts=experts,
        experts_per_token=_int(flat, *EXPERTS_PER_TOKEN_KEYS),
        expert_size=_int(flat, "moe_intermediate_size", "intermediate_size"),
    )


def active_parameters(total: int | None, shape: Architecture) -> int | None:
    if total is None or shape.family != "moe_decoder":
        return total
    needed: tuple[int | None, ...] = (
        shape.layers,
        shape.hidden_size,
        shape.experts,
        shape.experts_per_token,
        shape.expert_size,
    )
    if any(value is None for value in needed):
        return None
    idle_experts: int = (shape.experts or 0) - (shape.experts_per_token or 0)
    idle: int = (
        (shape.layers or 0) * idle_experts * 3 * (shape.hidden_size or 0) * (shape.expert_size or 0)
    )
    return max(total - idle, 0)


def chat_bytes(parameters: int, *, four_bit: bool) -> int:
    per_parameter: float = FOUR_BIT_BYTES_PER_PARAMETER if four_bit else HALF_BYTES_PER_PARAMETER
    return int(parameters * per_parameter) + RUNTIME_OVERHEAD_BYTES


def qlora_bytes(parameters: int) -> int:
    return int(parameters * QLORA_BYTES_PER_PARAMETER) + QLORA_FIXED_BYTES


def fit(required: int | None, available: int) -> Fit:
    if available <= 0:
        beyond_ram: bool = required is not None and required > hardware.ram_bytes()
        return Fit(
            verdict="too_large" if beyond_ram else "cpu_only",
            required_bytes=required,
            available_bytes=0,
        )
    if required is None:
        return Fit(verdict="unknown", required_bytes=None, available_bytes=available)
    verdict: Verdict
    if available >= required * HEADROOM:
        verdict = "fits"
    elif available >= required:
        verdict = "tight"
    else:
        verdict = "too_large"
    return Fit(verdict=verdict, required_bytes=required, available_bytes=available)


def supports_thinking(chat_template: str | None) -> bool:
    if not chat_template:
        return False
    return any(
        marker in chat_template for marker in ("enable_thinking", "<think>", "reasoning_content")
    )
