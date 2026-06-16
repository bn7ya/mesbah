"""Pydantic I/O for the architecture builder.

These describe a model the user is *defining from scratch* (no pretrained
weights). The same shape is persisted into ``Project.default_train_config
["architecture"]`` and the project's ``metadata.json``, and is later read by
``scripts/train_scratch.py`` to build a ``transformers`` config and random-init
the model.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

# Supported decoder families. Dense vs MoE drives the MLP block in the estimate
# and the config kwargs the trainer assembles.
DENSE_FAMILIES = ("llama", "qwen3", "mistral")
MOE_FAMILIES = ("qwen3_moe", "mixtral")
FAMILIES = DENSE_FAMILIES + MOE_FAMILIES


class ArchitectureSpec(BaseModel):
    """A from-scratch decoder-only LM architecture."""
    family: Literal["llama", "qwen3", "mistral", "qwen3_moe", "mixtral"] = "qwen3"
    num_hidden_layers: int = Field(default=12, ge=1, le=256)
    hidden_size: int = Field(default=768, ge=8, le=32768)
    num_attention_heads: int = Field(default=12, ge=1, le=256)
    num_key_value_heads: Optional[int] = Field(default=None, ge=1, le=256)  # None => = heads (MHA)
    intermediate_size: Optional[int] = Field(default=None, ge=8)            # None => ~4x hidden
    vocab_size: int = Field(default=32000, ge=1, le=1_000_000)
    max_position_embeddings: int = Field(default=2048, ge=8, le=2_000_000)
    tie_word_embeddings: bool = True
    # ── MoE only (ignored for dense families) ──
    num_experts: int = Field(default=8, ge=1, le=1024)
    num_experts_per_tok: int = Field(default=2, ge=1, le=1024)
    moe_intermediate_size: Optional[int] = Field(default=None, ge=8)

    @property
    def is_moe(self) -> bool:
        return self.family in MOE_FAMILIES


class ParamBreakdown(BaseModel):
    embeddings: int
    attention: int
    mlp: int
    other: int
    total_params: int
    active_params: int          # params actually used per token (MoE-aware)
    total_params_human: str
    active_params_human: str


class MemoryVerdict(BaseModel):
    # All in GB, bf16 weights + bf16 grads + 8-bit (paged) optimizer + activations.
    weights_gb: float
    gradients_gb: float
    optimizer_gb: float
    activation_gb: float
    total_gb: float
    gpu_vram_gb: int
    # Off-GPU footprint when training with ZeRO-Infinity offload: params + grads +
    # fp32 master + Adam states held in host RAM (or NVMe). This is the binding
    # constraint once paging is on — not VRAM.
    host_ram_gb: float
    # fits_vram      → trains entirely on the GPU.
    # cpu_offload    → too big for VRAM but the offloaded state fits host RAM.
    # nvme_offload   → exceeds RAM too; spills to NVMe (slowest, still finishes).
    # exceeds_disk   → implausible even with disk offload.
    verdict: Literal["fits_vram", "cpu_offload", "nvme_offload", "exceeds_disk"]
    paging_required: bool
    # True for every verdict except exceeds_disk: the run will complete (slowly).
    will_finish: bool


class FeasibilityEstimate(BaseModel):
    spec: ArchitectureSpec
    params: ParamBreakdown
    memory: MemoryVerdict
    warnings: list[str]
    suggested_gpu_budget_gb: int


class SolveHiddenRequest(BaseModel):
    """Suggest a hidden_size that lands near a target parameter count."""
    target_params: int = Field(ge=1)
    num_hidden_layers: int = Field(default=12, ge=1)
    vocab_size: int = Field(default=32000, ge=1)
    family: Literal["llama", "qwen3", "mistral", "qwen3_moe", "mixtral"] = "qwen3"
    num_experts: int = Field(default=8, ge=1)
