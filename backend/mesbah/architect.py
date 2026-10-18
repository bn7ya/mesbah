from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, Self, cast

from mesbah.sizing import RUNTIME_OVERHEAD_BYTES, Fit, fit
from mesbah.train.contract import JsonObject, JsonValue

type Family = Literal["dense_decoder", "moe_decoder", "encoder_decoder"]
type DesignCode = Literal[
    "missing",
    "invalid",
    "out_of_range",
    "not_divisible",
    "odd_head_dim",
    "too_many_active_experts",
    "tied_only",
]
type Precision = Literal["bf16_mixed"]
type Note = Literal["embeddings_dominate"]

FAMILIES: tuple[Family, ...] = ("dense_decoder", "moe_decoder", "encoder_decoder")
LIMITS: dict[str, tuple[int, int]] = {
    "layers": (1, 256),
    "encoder_layers": (1, 128),
    "decoder_layers": (1, 128),
    "hidden_size": (16, 65_536),
    "heads": (1, 1_024),
    "kv_heads": (1, 1_024),
    "intermediate_size": (16, 1_048_576),
    "vocab_size": (256, 1_048_576),
    "context_length": (64, 1_048_576),
    "experts": (2, 512),
    "experts_per_token": (1, 512),
}
COMMON_FIELDS: tuple[str, ...] = (
    "hidden_size",
    "heads",
    "intermediate_size",
    "vocab_size",
    "context_length",
)
FAMILY_FIELDS: dict[Family, tuple[str, ...]] = {
    "dense_decoder": ("layers",),
    "moe_decoder": ("layers", "experts", "experts_per_token"),
    "encoder_decoder": ("encoder_layers", "decoder_layers"),
}
RELATIVE_BUCKETS: int = 32
RELATIVE_MAX_DISTANCE: int = 128
ROUTER_AUX_LOSS_COEF: float = 0.01
BF16_BYTES: int = 2
ADAMW_BYTES_PER_PARAMETER: int = 16
ADAM_8BIT_BYTES_PER_PARAMETER: int = 10
LOGIT_BYTES: int = 12
SCORE_BYTES: int = 8
BACKWARD_FACTOR: int = 2
EMBEDDINGS_NOTE_SHARE: float = 0.5


class DesignError(ValueError):
    def __init__(self, code: DesignCode, field: str) -> None:
        super().__init__(f"{field}: {code}")
        self.code: DesignCode = code
        self.field: str = field


def _int(data: Mapping[str, object], key: str, required: bool) -> int:
    value: object = data.get(key)
    if value is None:
        if required:
            raise DesignError("missing", key)
        return 0
    if isinstance(value, bool) or not isinstance(value, int):
        raise DesignError("invalid", key)
    return value


def _in_range(value: int, key: str) -> None:
    low, high = LIMITS[key]
    if not low <= value <= high:
        raise DesignError("out_of_range", key)


@dataclass(frozen=True, kw_only=True)
class Design:
    family: Family
    hidden_size: int
    heads: int
    intermediate_size: int
    vocab_size: int
    context_length: int
    layers: int = 0
    kv_heads: int | None = None
    experts: int = 0
    experts_per_token: int = 0
    encoder_layers: int = 0
    decoder_layers: int = 0
    tie_embeddings: bool = True

    def __post_init__(self) -> None:
        for key in (*COMMON_FIELDS, *FAMILY_FIELDS[self.family]):
            _in_range(cast(int, getattr(self, key)), key)
        if self.hidden_size % self.heads:
            raise DesignError("not_divisible", "heads")
        if self.family == "encoder_decoder":
            if not self.tie_embeddings:
                raise DesignError("tied_only", "tie_embeddings")
            return
        _in_range(self.kv, "kv_heads")
        if self.heads % self.kv:
            raise DesignError("not_divisible", "kv_heads")
        # Rotary embeddings rotate the two halves of every head.
        if self.head_dim % 2:
            raise DesignError("odd_head_dim", "heads")
        if self.family == "moe_decoder" and self.experts_per_token > self.experts:
            raise DesignError("too_many_active_experts", "experts_per_token")

    @property
    def head_dim(self) -> int:
        return self.hidden_size // self.heads

    @property
    def kv(self) -> int:
        if self.family == "encoder_decoder" or self.kv_heads is None:
            return self.heads
        return self.kv_heads

    @classmethod
    def from_json(cls, data: object) -> Self:
        if not isinstance(data, dict):
            raise DesignError("invalid", "design")
        found: Mapping[str, object] = cast(Mapping[str, object], data)
        family_value: object = found.get("family")
        if family_value is None:
            raise DesignError("missing", "family")
        family: Family | None = next((name for name in FAMILIES if name == family_value), None)
        if family is None:
            raise DesignError("invalid", "family")
        needed: frozenset[str] = frozenset((*COMMON_FIELDS, *FAMILY_FIELDS[family]))

        def number(key: str) -> int:
            return _int(found, key, key in needed)

        tie: object = found.get("tie_embeddings", True)
        if not isinstance(tie, bool):
            raise DesignError("invalid", "tie_embeddings")
        return cls(
            family=family,
            layers=number("layers"),
            hidden_size=number("hidden_size"),
            heads=number("heads"),
            kv_heads=None if found.get("kv_heads") is None else _int(found, "kv_heads", True),
            intermediate_size=number("intermediate_size"),
            vocab_size=number("vocab_size"),
            context_length=number("context_length"),
            experts=number("experts"),
            experts_per_token=number("experts_per_token"),
            encoder_layers=number("encoder_layers"),
            decoder_layers=number("decoder_layers"),
            tie_embeddings=tie,
        )

    def to_json(self) -> JsonObject:
        return {
            "family": self.family,
            "layers": self.layers,
            "hidden_size": self.hidden_size,
            "heads": self.heads,
            "kv_heads": self.kv_heads,
            "intermediate_size": self.intermediate_size,
            "vocab_size": self.vocab_size,
            "context_length": self.context_length,
            "experts": self.experts,
            "experts_per_token": self.experts_per_token,
            "encoder_layers": self.encoder_layers,
            "decoder_layers": self.decoder_layers,
            "tie_embeddings": self.tie_embeddings,
        }


@dataclass(frozen=True)
class Parts:
    embeddings: int
    attention: int
    feed_forward: int
    router: int
    norms: int
    lm_head: int

    @property
    def total(self) -> int:
        return (
            self.embeddings
            + self.attention
            + self.feed_forward
            + self.router
            + self.norms
            + self.lm_head
        )


@dataclass(frozen=True)
class Counts:
    total: int
    active: int
    embeddings_share: float
    parts: Parts


@dataclass(frozen=True)
class Memory:
    precision: Precision
    weights_bytes: int
    adamw_bytes: int
    adamw_8bit_bytes: int
    activation_bytes: int
    training_bytes: int
    training_8bit_bytes: int
    fit: Fit
    fit_8bit: Fit


@dataclass(frozen=True)
class Preset:
    name: str
    design: Design
    counts: Counts


def _expert(design: Design) -> int:
    return 3 * design.hidden_size * design.intermediate_size


def _decoder_parts(design: Design) -> Parts:
    hidden: int = design.hidden_size
    layers: int = design.layers
    kv_width: int = design.kv * design.head_dim
    experts: int = design.experts if design.family == "moe_decoder" else 1
    embeddings: int = design.vocab_size * hidden
    return Parts(
        embeddings=embeddings,
        attention=layers * (2 * hidden * hidden + 2 * hidden * kv_width),
        feed_forward=layers * experts * _expert(design),
        router=layers * hidden * design.experts if design.family == "moe_decoder" else 0,
        norms=layers * (2 * hidden + 2 * design.head_dim) + hidden,
        lm_head=0 if design.tie_embeddings else embeddings,
    )


def _encoder_decoder_parts(design: Design) -> Parts:
    hidden: int = design.hidden_size
    encoder: int = design.encoder_layers
    decoder: int = design.decoder_layers
    projections: int = 4 * hidden * hidden
    position_bias: int = RELATIVE_BUCKETS * design.heads
    return Parts(
        embeddings=design.vocab_size * hidden,
        attention=(encoder + 2 * decoder) * projections + 2 * position_bias,
        feed_forward=(encoder + decoder) * _expert(design),
        router=0,
        norms=(2 * encoder + 1 + 3 * decoder + 1) * hidden,
        lm_head=0,
    )


def count(design: Design) -> Counts:
    parts: Parts = (
        _encoder_decoder_parts(design)
        if design.family == "encoder_decoder"
        else _decoder_parts(design)
    )
    idle: int = 0
    if design.family == "moe_decoder":
        idle = design.layers * (design.experts - design.experts_per_token) * _expert(design)
    return Counts(
        total=parts.total,
        active=parts.total - idle,
        embeddings_share=(parts.embeddings + parts.lm_head) / parts.total,
        parts=parts,
    )


def activation_bytes(design: Design, seq_len: int, batch: int) -> int:
    hidden: int = design.hidden_size
    tokens: int = seq_len * batch
    feed_forward: int = 4 * design.intermediate_size + 2 * hidden
    scores: int = 0
    layers: int
    width: int
    if design.family == "encoder_decoder":
        layers = design.encoder_layers + design.decoder_layers
        width = 2 * 6 * hidden + feed_forward
        # T5 adds its position bias to explicit scores, so no fused attention kernel applies.
        scores = 2 * design.heads * seq_len * seq_len * batch * SCORE_BYTES
    else:
        layers = design.layers
        if design.family == "moe_decoder":
            feed_forward = design.experts_per_token * 4 * design.intermediate_size
            feed_forward += 2 * hidden + 2 * design.experts
        width = 4 * hidden + 2 * design.kv * design.head_dim + feed_forward
    checkpoints: int = layers * tokens * hidden * BF16_BYTES
    recomputed: int = BACKWARD_FACTOR * width * tokens * BF16_BYTES
    logits: int = tokens * design.vocab_size * LOGIT_BYTES
    return checkpoints + recomputed + scores + logits


def memory(design: Design, vram_bytes: int, seq_len: int, batch: int) -> Memory:
    if seq_len < 1:
        raise DesignError("out_of_range", "seq_len")
    if batch < 1:
        raise DesignError("out_of_range", "batch")
    parameters: int = count(design).total
    activations: int = activation_bytes(design, seq_len, batch)
    adamw: int = parameters * ADAMW_BYTES_PER_PARAMETER
    eight_bit: int = parameters * ADAM_8BIT_BYTES_PER_PARAMETER
    training: int = adamw + activations + RUNTIME_OVERHEAD_BYTES
    training_8bit: int = eight_bit + activations + RUNTIME_OVERHEAD_BYTES
    return Memory(
        precision="bf16_mixed",
        weights_bytes=parameters * BF16_BYTES,
        adamw_bytes=adamw,
        adamw_8bit_bytes=eight_bit,
        activation_bytes=activations,
        training_bytes=training,
        training_8bit_bytes=training_8bit,
        fit=fit(training, vram_bytes),
        fit_8bit=fit(training_8bit, vram_bytes),
    )


def _decoder_config(design: Design, model_type: str) -> JsonObject:
    return {
        "model_type": model_type,
        "vocab_size": design.vocab_size,
        "hidden_size": design.hidden_size,
        "intermediate_size": design.intermediate_size,
        "num_hidden_layers": design.layers,
        "num_attention_heads": design.heads,
        "num_key_value_heads": design.kv,
        "head_dim": design.head_dim,
        "max_position_embeddings": design.context_length,
        "tie_word_embeddings": design.tie_embeddings,
    }


def to_hf_config(design: Design) -> JsonObject:
    if design.family == "dense_decoder":
        return _decoder_config(design, "qwen3")
    if design.family == "moe_decoder":
        no_dense_layers: list[JsonValue] = []
        return {
            **_decoder_config(design, "qwen3_moe"),
            "moe_intermediate_size": design.intermediate_size,
            "num_experts": design.experts,
            "num_experts_per_tok": design.experts_per_token,
            "norm_topk_prob": True,
            "decoder_sparse_step": 1,
            "mlp_only_layers": no_dense_layers,
            "output_router_logits": True,
            "router_aux_loss_coef": ROUTER_AUX_LOSS_COEF,
        }
    return {
        "model_type": "t5",
        "vocab_size": design.vocab_size,
        "d_model": design.hidden_size,
        "d_kv": design.head_dim,
        "d_ff": design.intermediate_size,
        "num_layers": design.encoder_layers,
        "num_decoder_layers": design.decoder_layers,
        "num_heads": design.heads,
        "relative_attention_num_buckets": RELATIVE_BUCKETS,
        "relative_attention_max_distance": RELATIVE_MAX_DISTANCE,
        "feed_forward_proj": "gated-gelu",
        "tie_word_embeddings": True,
        "dropout_rate": 0.0,
    }


PRESET_DESIGNS: tuple[tuple[str, Design], ...] = (
    (
        "tiny",
        Design(
            family="dense_decoder",
            layers=2,
            hidden_size=64,
            heads=4,
            kv_heads=2,
            intermediate_size=256,
            vocab_size=32_000,
            context_length=256,
        ),
    ),
    (
        "dense_100m",
        Design(
            family="dense_decoder",
            layers=12,
            hidden_size=768,
            heads=12,
            kv_heads=4,
            intermediate_size=2_048,
            vocab_size=32_000,
            context_length=2_048,
        ),
    ),
    (
        "dense_500m",
        Design(
            family="dense_decoder",
            layers=24,
            hidden_size=1_280,
            heads=20,
            kv_heads=4,
            intermediate_size=3_840,
            vocab_size=32_000,
            context_length=4_096,
        ),
    ),
    (
        "moe_1b",
        Design(
            family="moe_decoder",
            layers=16,
            hidden_size=1_024,
            heads=16,
            kv_heads=4,
            intermediate_size=2_304,
            vocab_size=32_000,
            context_length=4_096,
            experts=8,
            experts_per_token=2,
        ),
    ),
    (
        "t5_60m",
        Design(
            family="encoder_decoder",
            encoder_layers=6,
            decoder_layers=6,
            hidden_size=512,
            heads=8,
            intermediate_size=1_344,
            vocab_size=32_128,
            context_length=512,
        ),
    ),
)


def presets() -> tuple[Preset, ...]:
    return tuple(
        Preset(name=name, design=design, counts=count(design)) for name, design in PRESET_DESIGNS
    )


def vocabulary_note(design: Design) -> Note | None:
    return "embeddings_dominate" if count(design).embeddings_share > EMBEDDINGS_NOTE_SHARE else None
