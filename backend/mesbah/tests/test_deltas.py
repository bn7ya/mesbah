from __future__ import annotations

import json
import math
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

pytest.importorskip("torch")

import torch

from mesbah.train.contract import DeltaStats
from mesbah.train.deltas import adapter_size_bytes, delta_stats, lora_scale

if TYPE_CHECKING:
    from torch import Tensor

pytestmark: pytest.MarkDecorator = pytest.mark.ml

PREFIX: str = "base_model.model.model.layers"
Q: str = f"{PREFIX}.0.self_attn.q_proj"
V: str = f"{PREFIX}.0.self_attn.v_proj"
DOWN: str = f"{PREFIX}.1.mlp.down_proj"


def random_module(rank: int, inputs: int, outputs: int, seed: int) -> tuple[Tensor, Tensor]:
    generator: torch.Generator = torch.Generator().manual_seed(seed)
    a: Tensor = torch.randn(rank, inputs, generator=generator)
    b: Tensor = torch.randn(outputs, rank, generator=generator)
    return a, b


def write_adapter(
    path: Path,
    modules: dict[str, tuple[Tensor, Tensor]],
    rank: int,
    alpha: float,
    rslora: bool = False,
) -> Path:
    from safetensors.torch import save_file

    path.mkdir(parents=True)
    tensors: dict[str, Tensor] = {}
    for name, (a, b) in modules.items():
        tensors[f"{name}.lora_A.weight"] = a.contiguous()
        tensors[f"{name}.lora_B.weight"] = b.contiguous()
    save_file(tensors, str(path / "adapter_model.safetensors"))
    settings: dict[str, object] = {"r": rank, "lora_alpha": alpha, "use_rslora": rslora}
    (path / "adapter_config.json").write_text(json.dumps(settings), encoding="utf-8")
    return path


def dense(a: Tensor, b: Tensor, scale: float) -> Tensor:
    return scale * (b.double() @ a.double())


def test_the_norms_equal_the_dense_delta(tmp_path: Path) -> None:
    modules: dict[str, tuple[Tensor, Tensor]] = {
        Q: random_module(4, 16, 32, seed=1),
        DOWN: random_module(4, 24, 16, seed=2),
    }
    adapter: Path = write_adapter(tmp_path / "adapter", modules, rank=4, alpha=8)
    scale: float = 8 / 4

    stats: DeltaStats = delta_stats(adapter)

    expected: dict[str, float] = {
        name.removeprefix("base_model.model."): float(torch.linalg.norm(dense(a, b, scale)))
        for name, (a, b) in modules.items()
    }
    assert {layer.name: layer.norm for layer in stats.layers} == pytest.approx(expected)
    assert [(layer.layer, layer.module) for layer in stats.layers] == [
        (0, "q_proj"),
        (1, "down_proj"),
    ]
    assert stats.total_norm == pytest.approx(math.sqrt(sum(n**2 for n in expected.values())))
    assert stats.parameters == 4 * 16 + 32 * 4 + 4 * 24 + 16 * 4
    assert stats.rank == 4
    assert stats.change_from_parent is None


def test_the_change_from_a_parent_equals_the_dense_difference(tmp_path: Path) -> None:
    parent_modules: dict[str, tuple[Tensor, Tensor]] = {
        Q: random_module(2, 16, 32, seed=3),
        V: random_module(2, 16, 8, seed=4),
    }
    child_modules: dict[str, tuple[Tensor, Tensor]] = {
        Q: random_module(6, 16, 32, seed=5),
        DOWN: random_module(6, 24, 16, seed=6),
    }
    parent: Path = write_adapter(tmp_path / "parent", parent_modules, rank=2, alpha=4)
    child: Path = write_adapter(tmp_path / "child", child_modules, rank=6, alpha=12)

    stats: DeltaStats = delta_stats(child, parent)

    q_change: Tensor = dense(*child_modules[Q], scale=2.0) - dense(*parent_modules[Q], scale=2.0)
    expected: float = math.sqrt(
        float(torch.linalg.norm(q_change)) ** 2
        + float(torch.linalg.norm(dense(*parent_modules[V], scale=2.0))) ** 2
        + float(torch.linalg.norm(dense(*child_modules[DOWN], scale=2.0))) ** 2
    )
    assert stats.change_from_parent == pytest.approx(expected)


def test_an_adapter_is_no_change_from_itself(tmp_path: Path) -> None:
    adapter: Path = write_adapter(
        tmp_path / "adapter", {Q: random_module(4, 16, 32, seed=7)}, rank=4, alpha=8
    )

    assert delta_stats(adapter, adapter).change_from_parent == pytest.approx(0.0, abs=1e-9)


def test_rslora_scales_by_the_square_root_of_the_rank(tmp_path: Path) -> None:
    a, b = random_module(16, 8, 8, seed=8)
    adapter: Path = write_adapter(tmp_path / "adapter", {Q: (a, b)}, rank=16, alpha=8, rslora=True)

    stats: DeltaStats = delta_stats(adapter)

    assert lora_scale(8, 16, rslora=True) == 2.0
    assert lora_scale(8, 16, rslora=False) == 0.5
    assert stats.total_norm == pytest.approx(float(torch.linalg.norm(dense(a, b, scale=2.0))))


def test_the_size_counts_every_file(tmp_path: Path) -> None:
    adapter: Path = write_adapter(
        tmp_path / "adapter", {Q: random_module(4, 16, 32, seed=9)}, rank=4, alpha=8
    )

    assert adapter_size_bytes(adapter) == sum(path.stat().st_size for path in adapter.iterdir())
