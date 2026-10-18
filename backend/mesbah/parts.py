from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata

PARTS: tuple[tuple[str, str], ...] = (
    ("torch", "training"),
    ("transformers", "training"),
    ("peft", "training"),
    ("trl", "training"),
    ("accelerate", "training"),
    ("bitsandbytes", "quantization"),
    ("unsloth", "speed"),
    ("gguf", "gguf"),
)


@dataclass(frozen=True)
class Part:
    name: str
    purpose: str
    version: str | None

    @property
    def cuda(self) -> bool | None:
        if self.name != "torch" or self.version is None:
            return None
        if "+cpu" in self.version:
            return False
        return True if "+cu" in self.version else None


def installed(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def parts() -> tuple[Part, ...]:
    return tuple(
        Part(name=name, purpose=purpose, version=installed(name)) for name, purpose in PARTS
    )
