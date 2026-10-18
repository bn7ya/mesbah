from __future__ import annotations

from mesbah import sizing

GIB: int = 1024**3

QWEN3_8B: dict[str, object] = {
    "architectures": ["Qwen3ForCausalLM"],
    "model_type": "qwen3",
    "num_hidden_layers": 36,
    "hidden_size": 4096,
    "num_attention_heads": 32,
    "num_key_value_heads": 8,
    "vocab_size": 151936,
    "max_position_embeddings": 40960,
}

QWEN3_30B_A3B: dict[str, object] = {
    "architectures": ["Qwen3MoeForCausalLM"],
    "model_type": "qwen3_moe",
    "num_hidden_layers": 48,
    "hidden_size": 2048,
    "num_experts": 128,
    "num_experts_per_tok": 8,
    "moe_intermediate_size": 768,
    "max_position_embeddings": 40960,
}


def test_a_dense_decoder() -> None:
    shape: sizing.Architecture = sizing.architecture(QWEN3_8B)

    assert shape.family == "dense_decoder"
    assert (shape.layers, shape.context_length, shape.kv_heads) == (36, 40960, 8)


def test_a_mixture_of_experts_and_its_active_parameters() -> None:
    shape: sizing.Architecture = sizing.architecture(QWEN3_30B_A3B)
    active: int | None = sizing.active_parameters(30_532_122_624, shape)

    assert shape.family == "moe_decoder"
    assert (shape.experts, shape.experts_per_token) == (128, 8)
    assert active is not None
    assert 2_500_000_000 < active < 4_000_000_000


def test_an_encoder_decoder() -> None:
    assert sizing.architecture({"model_type": "t5", "d_model": 512}).family == "encoder_decoder"


def test_a_multimodal_config_reads_its_text_part() -> None:
    shape: sizing.Architecture = sizing.architecture(
        {"model_type": "gemma3", "text_config": {"num_hidden_layers": 34, "hidden_size": 2560}}
    )

    assert (shape.layers, shape.hidden_size) == (34, 2560)


def test_an_8b_model_on_a_16_gb_card() -> None:
    parameters: int = 8_190_735_360

    assert sizing.fit(sizing.chat_bytes(parameters, four_bit=True), 16 * GIB).verdict == "fits"
    assert (
        sizing.fit(sizing.chat_bytes(parameters, four_bit=False), 16 * GIB).verdict == "too_large"
    )
    assert sizing.fit(sizing.qlora_bytes(parameters), 16 * GIB).verdict == "fits"


def test_a_14b_model_is_tight_for_qlora_on_16_gb() -> None:
    assert sizing.fit(sizing.qlora_bytes(14_768_307_200), 16 * GIB).verdict == "tight"


def test_no_gpu_means_cpu_only() -> None:
    assert sizing.fit(5 * GIB, 0).verdict == "cpu_only"


def test_thinking_is_read_from_the_chat_template() -> None:
    assert sizing.supports_thinking("{% if enable_thinking %}<think>{% endif %}")
    assert not sizing.supports_thinking("{{ message.content }}")
    assert not sizing.supports_thinking(None)
