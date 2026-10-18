from __future__ import annotations

import json
from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from mesbah import hardware
from mesbah.architect import (
    ADAM_8BIT_BYTES_PER_PARAMETER,
    ADAMW_BYTES_PER_PARAMETER,
    Counts,
    Design,
    DesignError,
    Memory,
    Preset,
    count,
    memory,
    presets,
    to_hf_config,
    vocabulary_note,
)
from mesbah.sizing import active_parameters, architecture
from mesbah.train.contract import JsonObject

if TYPE_CHECKING:
    from torch.nn import Module
    from transformers import PreTrainedConfig

GIB: int = 1024**3
DENSE: Design = Design(
    family="dense_decoder",
    layers=2,
    hidden_size=64,
    heads=4,
    kv_heads=2,
    intermediate_size=128,
    vocab_size=1_000,
    context_length=128,
)
MOE: Design = Design(
    family="moe_decoder",
    layers=2,
    hidden_size=64,
    heads=4,
    kv_heads=2,
    intermediate_size=32,
    vocab_size=1_000,
    context_length=128,
    experts=8,
    experts_per_token=2,
)
T5: Design = Design(
    family="encoder_decoder",
    encoder_layers=2,
    decoder_layers=3,
    hidden_size=64,
    heads=4,
    intermediate_size=128,
    vocab_size=1_000,
    context_length=128,
)
EXTRA: tuple[Design, ...] = (
    DENSE,
    replace(DENSE, tie_embeddings=False),
    MOE,
    replace(MOE, tie_embeddings=False, kv_heads=None),
    T5,
)


def by_name() -> dict[str, Preset]:
    return {preset.name: preset for preset in presets()}


def test_the_presets_cover_each_family_at_their_sizes() -> None:
    found: dict[str, Preset] = by_name()
    sizes: dict[str, Counts] = {name: preset.counts for name, preset in found.items()}

    assert list(found) == ["tiny", "dense_100m", "dense_500m", "moe_1b", "t5_60m"]
    assert sizes["tiny"].total < 5_000_000
    assert 95e6 < sizes["dense_100m"].total < 105e6
    assert 470e6 < sizes["dense_500m"].total < 530e6
    assert 0.9e9 < sizes["moe_1b"].total < 1.1e9
    assert 270e6 < sizes["moe_1b"].active < 330e6
    assert 55e6 < sizes["t5_60m"].total < 65e6
    assert found["moe_1b"].design.family == "moe_decoder"
    assert found["t5_60m"].design.family == "encoder_decoder"
    assert all(preset.counts == count(preset.design) for preset in found.values())


@pytest.mark.parametrize("design", [preset.design for preset in presets()] + list(EXTRA))
def test_a_design_round_trips_through_json(design: Design) -> None:
    written: str = json.dumps(design.to_json())

    assert Design.from_json(json.loads(written)) == design


def test_an_encoder_decoder_needs_no_decoder_only_fields() -> None:
    data: JsonObject = {
        "family": "encoder_decoder",
        "encoder_layers": 2,
        "decoder_layers": 2,
        "hidden_size": 64,
        "heads": 4,
        "intermediate_size": 128,
        "vocab_size": 1_000,
        "context_length": 128,
    }

    design: Design = Design.from_json(data)

    assert (design.layers, design.kv_heads, design.tie_embeddings) == (0, None, True)
    assert design.kv == design.heads


@pytest.mark.parametrize(
    ("design", "changes", "code", "field"),
    [
        (DENSE, {"hidden_size": 66}, "not_divisible", "heads"),
        (DENSE, {"hidden_size": 100}, "odd_head_dim", "heads"),
        (DENSE, {"kv_heads": 3}, "not_divisible", "kv_heads"),
        (DENSE, {"kv_heads": 0}, "out_of_range", "kv_heads"),
        (DENSE, {"hidden_size": 96, "heads": 32, "kv_heads": 8}, "odd_head_dim", "heads"),
        (DENSE, {"layers": 0}, "out_of_range", "layers"),
        (DENSE, {"vocab_size": 10}, "out_of_range", "vocab_size"),
        (DENSE, {"context_length": 2**21}, "out_of_range", "context_length"),
        (MOE, {"experts_per_token": 9}, "too_many_active_experts", "experts_per_token"),
        (MOE, {"experts": 1}, "out_of_range", "experts"),
        (T5, {"tie_embeddings": False}, "tied_only", "tie_embeddings"),
        (T5, {"decoder_layers": 0}, "out_of_range", "decoder_layers"),
    ],
)
def test_a_design_that_cannot_be_built_names_its_field(
    design: Design, changes: dict[str, int | bool], code: str, field: str
) -> None:
    data: JsonObject = {**design.to_json(), **changes}

    with pytest.raises(DesignError) as caught:
        Design.from_json(data)

    assert (caught.value.code, caught.value.field) == (code, field)


@pytest.mark.parametrize(
    ("changes", "code", "field"),
    [
        ({"family": None}, "missing", "family"),
        ({"family": "rnn"}, "invalid", "family"),
        ({"hidden_size": None}, "missing", "hidden_size"),
        ({"hidden_size": "64"}, "invalid", "hidden_size"),
        ({"heads": True}, "invalid", "heads"),
        ({"layers": None}, "missing", "layers"),
        ({"tie_embeddings": "yes"}, "invalid", "tie_embeddings"),
    ],
)
def test_a_malformed_design_is_a_design_error(
    changes: dict[str, object], code: str, field: str
) -> None:
    data: dict[str, object] = {**DENSE.to_json(), **changes}

    with pytest.raises(DesignError) as caught:
        Design.from_json(data)

    assert (caught.value.code, caught.value.field) == (code, field)


def test_a_dense_count_adds_up_by_part() -> None:
    counts: Counts = count(DENSE)
    untied: Counts = count(replace(DENSE, tie_embeddings=False))

    assert counts.parts.embeddings == 1_000 * 64
    assert counts.parts.attention == 2 * (2 * 64 * 64 + 2 * 64 * 32)
    assert counts.parts.feed_forward == 2 * 3 * 64 * 128
    assert counts.parts.norms == 2 * (2 * 64 + 2 * 16) + 64
    assert (counts.parts.router, counts.parts.lm_head) == (0, 0)
    assert counts.total == counts.active == counts.parts.total == 138_112
    assert untied.parts.lm_head == 64_000
    assert untied.total == counts.total + 64_000
    assert untied.embeddings_share == pytest.approx(128_000 / untied.total)


def test_a_mixture_uses_only_its_chosen_experts_per_token() -> None:
    counts: Counts = count(MOE)
    expert: int = 3 * 64 * 32

    assert counts.parts.feed_forward == 2 * 8 * expert
    assert counts.parts.router == 2 * 8 * 64
    assert counts.total - counts.active == 2 * (8 - 2) * expert
    assert (
        active_parameters(counts.total, architecture(dict[str, object](to_hf_config(MOE))))
        == counts.active
    )


def test_an_encoder_decoder_shares_its_embeddings_with_the_head() -> None:
    counts: Counts = count(T5)

    assert counts.parts.lm_head == 0
    assert counts.parts.attention == (2 + 2 * 3) * 4 * 64 * 64 + 2 * 32 * 4
    assert counts.total == 319_168


def test_training_memory_is_bytes_per_parameter_plus_activations() -> None:
    parameters: int = count(DENSE).total
    short: Memory = memory(DENSE, 24 * GIB, seq_len=128, batch=1)
    long: Memory = memory(DENSE, 24 * GIB, seq_len=1024, batch=4)

    assert short.precision == "bf16_mixed"
    assert short.weights_bytes == 2 * parameters
    assert short.adamw_bytes == ADAMW_BYTES_PER_PARAMETER * parameters
    assert short.adamw_8bit_bytes == ADAM_8BIT_BYTES_PER_PARAMETER * parameters
    assert short.training_bytes - short.training_8bit_bytes == 6 * parameters
    assert short.training_bytes > short.adamw_bytes + short.activation_bytes
    assert long.activation_bytes > 8 * short.activation_bytes
    assert short.fit.verdict == "fits"


def test_the_fit_verdict_reads_the_memory_available(monkeypatch: pytest.MonkeyPatch) -> None:
    big: Design = by_name()["dense_500m"].design
    monkeypatch.setattr(hardware, "ram_bytes", lambda: 256 * GIB)

    assert memory(big, 0, 2_048, 1).fit.verdict == "cpu_only"
    assert memory(big, 4 * GIB, 2_048, 1).fit.verdict == "too_large"
    assert memory(big, 4 * GIB, 2_048, 1).fit_8bit.verdict == "too_large"
    assert memory(big, 80 * GIB, 2_048, 1).fit.verdict == "fits"


def test_without_a_gpu_a_design_beyond_the_ram_is_too_large(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    big: Design = by_name()["dense_500m"].design
    monkeypatch.setattr(hardware, "ram_bytes", lambda: 4 * GIB)

    assert memory(big, 0, 2_048, 1).fit.verdict == "too_large"
    assert memory(big, 0, 2_048, 1).fit_8bit.verdict == "too_large"


def test_a_mixture_holds_every_expert_in_memory() -> None:
    assert memory(MOE, GIB, 128, 1).weights_bytes == 2 * count(MOE).total


def test_memory_needs_a_sequence_and_a_batch() -> None:
    with pytest.raises(DesignError) as caught:
        memory(DENSE, GIB, 0, 1)

    assert caught.value.field == "seq_len"


def test_each_family_maps_to_its_transformers_config() -> None:
    dense: JsonObject = to_hf_config(DENSE)
    moe: JsonObject = to_hf_config(MOE)
    t5: JsonObject = to_hf_config(T5)

    assert dense == {
        "model_type": "qwen3",
        "vocab_size": 1_000,
        "hidden_size": 64,
        "intermediate_size": 128,
        "num_hidden_layers": 2,
        "num_attention_heads": 4,
        "num_key_value_heads": 2,
        "head_dim": 16,
        "max_position_embeddings": 128,
        "tie_word_embeddings": True,
    }
    assert moe["model_type"] == "qwen3_moe"
    assert (moe["num_experts"], moe["num_experts_per_tok"], moe["moe_intermediate_size"]) == (
        8,
        2,
        32,
    )
    assert moe["output_router_logits"] is True
    assert isinstance(moe["router_aux_loss_coef"], float)
    assert moe["router_aux_loss_coef"] > 0
    assert t5["model_type"] == "t5"
    assert t5["feed_forward_proj"] == "gated-gelu"
    assert (t5["num_layers"], t5["num_decoder_layers"], t5["d_kv"]) == (2, 3, 16)


def test_a_model_made_mostly_of_vocabulary_gets_a_note() -> None:
    found: dict[str, Preset] = by_name()

    assert vocabulary_note(found["tiny"].design) == "embeddings_dominate"
    assert vocabulary_note(found["dense_100m"].design) is None
    assert vocabulary_note(found["moe_1b"].design) is None


@pytest.mark.ml
@pytest.mark.parametrize("design", [preset.design for preset in presets()] + list(EXTRA))
def test_the_counts_match_the_transformers_models(design: Design) -> None:
    pytest.importorskip("torch")
    pytest.importorskip("transformers")
    import torch
    from transformers import AutoConfig, AutoModelForCausalLM, AutoModelForSeq2SeqLM

    settings: JsonObject = dict(to_hf_config(design))
    model_type: str = str(settings.pop("model_type"))
    shape: PreTrainedConfig = AutoConfig.for_model(model_type, **settings)
    seq2seq: bool = design.family == "encoder_decoder"

    with torch.device("meta"):
        model: Module = (
            AutoModelForSeq2SeqLM.from_config(shape)
            if seq2seq
            else AutoModelForCausalLM.from_config(shape)
        )

    counts: Counts = count(design)
    assert sum(parameter.numel() for parameter in model.parameters()) == counts.total
    assert model.get_input_embeddings().weight.numel() == counts.parts.embeddings
