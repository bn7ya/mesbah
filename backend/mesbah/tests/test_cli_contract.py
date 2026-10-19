from __future__ import annotations

import argparse
import re
from pathlib import Path

import pytest

from contracts import Contract
from mesbah.cli import build_parser

APPS: Path = Path(__file__).resolve().parents[2] / "apps"
SKIPPED: tuple[type[argparse.Action], ...] = (argparse._HelpAction, argparse._VersionAction)
ACTION_WORDS: re.Pattern[str] = re.compile(r"(?<=[a-z])(?=[A-Z])")


def option(action: argparse.Action) -> dict[str, object]:
    kind: object = action.type
    return {
        "flags": action.option_strings or [action.dest],
        "dest": action.dest,
        "default": action.default,
        "type": getattr(kind, "__name__", None),
        "nargs": action.nargs if isinstance(action.nargs, int | str) else None,
        "required": action.required,
        "action": ACTION_WORDS.sub("_", type(action).__name__.strip("_"))
        .removesuffix("_Action")
        .lower(),
    }


def described(parser: argparse.ArgumentParser) -> dict[str, object]:
    options: list[dict[str, object]] = []
    commands: dict[str, object] = {}
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            commands = {name: described(sub) for name, sub in action.choices.items()}
        elif not isinstance(action, SKIPPED):
            options.append(option(action))
    return {"options": options, "commands": commands}


@pytest.mark.contract
def test_the_command_line_is_what_the_release_promises(
    contract: Contract, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    management: list[str] = sorted(
        path.stem
        for path in APPS.glob("*/management/commands/*.py")
        if not path.stem.startswith("_")
    )

    contract.check(
        "cli.json",
        {"mesbah": described(build_parser()), "mesbah manage": {"mesbah's own": management}},
    )
