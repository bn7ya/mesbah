from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self, cast

type ExportKind = Literal["merged", "gguf"]
type OutType = Literal["f16", "bf16", "q8_0"]
type ExportState = Literal["completed", "failed"]

KINDS: tuple[ExportKind, ...] = ("merged", "gguf")
OUT_TYPES: tuple[OutType, ...] = ("f16", "bf16", "q8_0")


class ExportContractError(ValueError):
    pass


def _text(data: dict[str, object], key: str, *, optional: bool = False) -> str | None:
    value: object = data.get(key)
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value:
        raise ExportContractError(f"{key!r} must be a non-empty string")
    return value


@dataclass(frozen=True)
class ExportConfig:
    kind: ExportKind
    base_path: str
    output_dir: str
    status_path: str
    tools_dir: str
    adapter_path: str | None = None
    out_type: OutType = "f16"
    name: str = "model"
    system_prompt: str = ""

    @classmethod
    def from_json(cls, data: object) -> Self:
        if not isinstance(data, dict):
            raise ExportContractError("the export config must be an object")
        found: dict[str, object] = cast(dict[str, object], data)
        kind: object = found.get("kind")
        out_type: object = found.get("out_type", "f16")
        if kind not in KINDS:
            raise ExportContractError(f"'kind' must be one of {KINDS}")
        if out_type not in OUT_TYPES:
            raise ExportContractError(f"'out_type' must be one of {OUT_TYPES}")
        return cls(
            kind=cast(ExportKind, kind),
            base_path=str(_text(found, "base_path")),
            output_dir=str(_text(found, "output_dir")),
            status_path=str(_text(found, "status_path")),
            tools_dir=str(_text(found, "tools_dir")),
            adapter_path=_text(found, "adapter_path", optional=True),
            out_type=cast(OutType, out_type),
            name=_text(found, "name", optional=True) or "model",
            system_prompt=str(found.get("system_prompt") or ""),
        )

    def to_json(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "base_path": self.base_path,
            "output_dir": self.output_dir,
            "status_path": self.status_path,
            "tools_dir": self.tools_dir,
            "adapter_path": self.adapter_path,
            "out_type": self.out_type,
            "name": self.name,
            "system_prompt": self.system_prompt,
        }

    @classmethod
    def read(cls, path: Path) -> Self:
        return cls.from_json(json.loads(path.read_text(encoding="utf-8")))

    def write(self, path: Path) -> None:
        _write(path, self.to_json())


@dataclass(frozen=True)
class ExportStatus:
    status: ExportState
    output: str | None = None
    size_bytes: int = 0
    error_code: str | None = None
    error_detail: str = ""

    @classmethod
    def read(cls, path: Path) -> Self:
        found: object = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(found, dict) or found.get("status") not in ("completed", "failed"):
            raise ExportContractError("not an export status")
        data: dict[str, object] = cast(dict[str, object], found)
        size: object = data.get("size_bytes", 0)
        output: object = data.get("output")
        code: object = data.get("error_code")
        return cls(
            status=cast(ExportState, data["status"]),
            output=output if isinstance(output, str) else None,
            size_bytes=size if isinstance(size, int) else 0,
            error_code=code if isinstance(code, str) else None,
            error_detail=str(data.get("error_detail") or ""),
        )

    def write(self, path: Path) -> None:
        _write(
            path,
            {
                "status": self.status,
                "output": self.output,
                "size_bytes": self.size_bytes,
                "error_code": self.error_code,
                "error_detail": self.error_detail,
            },
        )


def _write(path: Path, data: dict[str, object]) -> None:
    partial: Path = path.with_suffix(path.suffix + ".partial")
    partial.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(partial, path)
