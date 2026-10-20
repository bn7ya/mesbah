from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

GOLDENS: Path = Path(__file__).resolve().parent
SHOWN_LINES: int = 80
ACCEPTING: str = (
    "If the change is meant, run `pytest --update-contracts`, review "
    "`git diff backend/contracts/`, and say what changed under `### Contracts` in CHANGELOG.md, "
    "in the same commit."
)


def canonical(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


@dataclass(frozen=True)
class Contract:
    update: bool

    def check(self, name: str, value: object) -> None:
        path: Path = GOLDENS / name
        written: str = canonical(value)
        if self.update:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(written, encoding="utf-8")
            return
        if not path.is_file():
            pytest.fail(f"contracts/{name} is missing. Run `pytest --update-contracts`.", False)
        kept: str = path.read_text(encoding="utf-8")
        if kept == written:
            return
        changes: list[str] = list(
            difflib.unified_diff(
                kept.splitlines(),
                written.splitlines(),
                f"contracts/{name}",
                "the code",
                lineterm="",
            )
        )
        shown: str = "\n".join(changes[:SHOWN_LINES])
        if len(changes) > SHOWN_LINES:
            shown += f"\n… and {len(changes) - SHOWN_LINES} more lines"
        pytest.fail(f"contracts/{name} no longer matches the code:\n{shown}\n\n{ACCEPTING}", False)
