from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from mesbah.train.contract import DeltaStats, LayerDelta

if TYPE_CHECKING:
    from torch import Tensor

ADAPTER_WEIGHTS: str = "adapter_model.safetensors"
ADAPTER_CONFIG: str = "adapter_config.json"
LORA_KEY: re.Pattern[str] = re.compile(
    r"^(?P<module>.+)\.lora_(?P<side>[AB])(?:\.default)?\.weight$"
)
LAYER_INDEX: re.Pattern[str] = re.compile(r"\.(?:layers|layer|h|blocks)\.(\d+)\.")
PEFT_PREFIX: str = "base_model.model."


@dataclass(frozen=True)
class AdapterSettings:
    alpha: float
    rslora: bool
    alpha_pattern: Mapping[str, float]


@dataclass(frozen=True)
class LoraModule:
    a: Tensor
    b: Tensor
    scale: float

    @property
    def rank(self) -> int:
        return int(self.a.shape[0])


def lora_scale(alpha: float, rank: int, rslora: bool) -> float:
    return alpha / math.sqrt(rank) if rslora else alpha / rank


def _pattern_value(patterns: Mapping[str, float], module: str, default: float) -> float:
    for pattern, value in patterns.items():
        if re.match(rf"(.*\.)?({pattern})$", module):
            return value
    return default


def read_settings(adapter_dir: Path) -> AdapterSettings:
    parsed: object = json.loads((adapter_dir / ADAPTER_CONFIG).read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError(f"{adapter_dir / ADAPTER_CONFIG} is not a JSON object")
    found: Mapping[str, object] = cast(Mapping[str, object], parsed)
    alpha: object = found.get("lora_alpha", 8)
    patterns: object = found.get("alpha_pattern") or {}
    if not isinstance(alpha, int | float) or not isinstance(patterns, dict):
        raise ValueError(f"{adapter_dir / ADAPTER_CONFIG} has no usable lora_alpha")
    return AdapterSettings(
        alpha=float(alpha),
        rslora=found.get("use_rslora") is True,
        alpha_pattern={
            str(key): float(value)
            for key, value in cast(Mapping[object, object], patterns).items()
            if isinstance(value, int | float)
        },
    )


def lora_pairs(tensors: Mapping[str, Tensor]) -> dict[str, tuple[Tensor, Tensor]]:
    sides: dict[str, dict[str, Tensor]] = {}
    for key, tensor in tensors.items():
        match: re.Match[str] | None = LORA_KEY.match(key)
        if match is not None:
            sides.setdefault(match["module"], {})[match["side"]] = tensor
    return {
        module: (found["A"], found["B"])
        for module, found in sides.items()
        if "A" in found and "B" in found
    }


def module_scale(settings: AdapterSettings, module: str, rank: int) -> float:
    alpha: float = _pattern_value(settings.alpha_pattern, module, settings.alpha)
    return lora_scale(alpha, rank, settings.rslora)


def read_adapter(adapter_dir: Path) -> dict[str, LoraModule]:
    from safetensors.torch import load_file

    settings: AdapterSettings = read_settings(adapter_dir)
    tensors: dict[str, Tensor] = load_file(str(adapter_dir / ADAPTER_WEIGHTS))
    modules: dict[str, LoraModule] = {}
    for name, (a, b) in lora_pairs(tensors).items():
        if a.shape[0] != b.shape[1]:
            raise ValueError(f"{name}: lora_A has rank {a.shape[0]}, lora_B has {b.shape[1]}")
        rank: int = int(a.shape[0])
        modules[name] = LoraModule(
            a=a.double(), b=b.double(), scale=module_scale(settings, name, rank)
        )
    return modules


def squared_norm(module: LoraModule) -> float:
    import torch

    gram: Tensor = (module.b.T @ module.b) @ (module.a @ module.a.T)
    return module.scale**2 * float(torch.trace(gram))


def inner_product(first: LoraModule, second: LoraModule) -> float:
    import torch

    cross: Tensor = (first.b.T @ second.b) @ (second.a @ first.a.T)
    return first.scale * second.scale * float(torch.trace(cross))


def _layer_delta(name: str, norm: float) -> LayerDelta:
    short: str = name.removeprefix(PEFT_PREFIX)
    index: re.Match[str] | None = LAYER_INDEX.search(f".{short}.")
    return LayerDelta(
        name=short,
        layer=None if index is None else int(index.group(1)),
        module=short.rsplit(".", 1)[-1],
        norm=norm,
    )


def change_between(modules: Mapping[str, LoraModule], others: Mapping[str, LoraModule]) -> float:
    total: float = 0.0
    for name in modules.keys() | others.keys():
        mine: LoraModule | None = modules.get(name)
        theirs: LoraModule | None = others.get(name)
        if mine is not None and theirs is not None:
            total += squared_norm(mine) + squared_norm(theirs) - 2 * inner_product(mine, theirs)
        elif mine is not None:
            total += squared_norm(mine)
        elif theirs is not None:
            total += squared_norm(theirs)
    return math.sqrt(max(total, 0.0))


def delta_stats(adapter_dir: Path, parent_dir: Path | None = None) -> DeltaStats:
    modules: dict[str, LoraModule] = read_adapter(adapter_dir)
    norms: dict[str, float] = {
        name: math.sqrt(max(squared_norm(module), 0.0)) for name, module in modules.items()
    }
    layers: list[LayerDelta] = sorted(
        (_layer_delta(name, norm) for name, norm in norms.items()),
        key=lambda entry: (-1 if entry.layer is None else entry.layer, entry.name),
    )
    return DeltaStats(
        layers=tuple(layers),
        total_norm=math.sqrt(sum(norm**2 for norm in norms.values())),
        parameters=sum(int(module.a.numel() + module.b.numel()) for module in modules.values()),
        rank=max((module.rank for module in modules.values()), default=0),
        change_from_parent=(
            None if parent_dir is None else change_between(modules, read_adapter(parent_dir))
        ),
    )


def adapter_size_bytes(adapter_dir: Path) -> int:
    return sum(path.stat().st_size for path in adapter_dir.rglob("*") if path.is_file())
