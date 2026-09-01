#!/usr/bin/env python3
"""PostToolUse hook: enforce the mechanical rules from .claude/docs/design-pattern.md.

Runs after Edit/Write/MultiEdit. Reads the touched file and scans for the
violations that are cheap to detect with a regex. Exits 2 with the violated
rule on stderr, which Claude Code feeds back to the model so it fixes the
problem before moving on.

Rules that need real understanding (dead code, deprecated APIs, whether a
change is a "complete slice") are not checked here -- they belong to
`cleaner` and code review.

Scoped to what mesbah's own conventions actually require: there is no
`.scss`-token styling system here (Tailwind utility classes only, see
frontend/CLAUDE.md), so there is no raw-px rule to enforce -- only the
Angular/PrimeNG and Django/DRF layering rules that apply to this codebase.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

# ---------------------------------------------------------------- rule model


@dataclass(frozen=True)
class Rule:
    id: str
    pattern: re.Pattern[str]
    message: str
    applies: Callable[[Path], bool]


def is_frontend_ts(path: Path) -> bool:
    return path.suffix == ".ts" and ".spec." not in path.name


def is_frontend_markup(path: Path) -> bool:
    return path.suffix in {".ts", ".html"} and ".spec." not in path.name


def is_django_app_python(path: Path) -> bool:
    if path.suffix != ".py":
        return False
    parts = path.parts
    if "apps" not in parts:
        return False
    # Repositories are the one place the ORM is allowed.
    if "repositories" in parts:
        return False
    # Migrations are generated and legitimately reference the ORM.
    if "migrations" in parts:
        return False
    return True


RULES: tuple[Rule, ...] = (
    Rule(
        id="Angular: no setTimeout",
        pattern=re.compile(r"\bsetTimeout\s*\("),
        message=(
            "setTimeout is not allowed.\n"
            "  Model the timing in state with signals, or use a PrimeNG API that\n"
            "  already expresses the delay."
        ),
        applies=is_frontend_ts,
    ),
    Rule(
        id="Angular: no native dialogs",
        pattern=re.compile(r"(?:\bwindow\s*\.\s*)?\b(?:confirm|alert|prompt)\s*\("),
        message=(
            "native browser dialog.\n"
            "  Use the PrimeNG equivalent: p-confirmdialog for confirm(), p-toast or\n"
            "  p-message for alert(), a p-dialog with a p-inputtext for prompt()."
        ),
        applies=is_frontend_ts,
    ),
    Rule(
        id="Angular: no native dialogs",
        pattern=re.compile(r"<dialog[\s>]|<input[^>]*type\s*=\s*[\"']radio[\"']"),
        message=(
            "native <dialog> or bare radio input.\n"
            "  Use p-dialog and p-radiobutton."
        ),
        applies=is_frontend_markup,
    ),
    Rule(
        id="Django: ORM only in repositories",
        pattern=re.compile(r"\.objects\s*\."),
        message=(
            "ORM access outside a repository.\n"
            "  Every .objects. call belongs in apps/<feature>/repositories/.\n"
            "  Views call services; services call repositories; repositories call the ORM."
        ),
        applies=is_django_app_python,
    ),
    Rule(
        id="Django: no raw SQL",
        pattern=re.compile(r"\b(?:raw|extra)\s*\(\s*[\"']|\bcursor\s*\.\s*execute\s*\("),
        message=(
            "raw SQL in application code.\n"
            "  Express it through the ORM. If that is genuinely impossible, put it in a\n"
            "  repository method with a comment explaining why, and have db_engineer\n"
            "  sign off with benchmark numbers."
        ),
        applies=is_django_app_python,
    ),
    Rule(
        id="Django: soft delete only",
        pattern=re.compile(r"\.hard_delete\s*\(|\.purge\s*\(|\bqueryset\s*\.\s*delete\s*\(\s*\)"),
        message=(
            "hard delete.\n"
            "  delete() must set deleted_at (BaseModel already does this). Removing rows\n"
            "  for real (.purge()) is a data migration, never an application action."
        ),
        applies=is_django_app_python,
    ),
)

# ------------------------------------------------------------------- scanning

COMMENT_PREFIXES = ("//", "#", "*", "/*", "<!--")


def offending_lines(text: str, rule: Rule) -> Iterable[tuple[int, str]]:
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(COMMENT_PREFIXES):
            continue
        if rule.pattern.search(line):
            yield number, stripped


def touched_path(event: dict) -> Path | None:
    tool_input = event.get("tool_input") or {}
    raw = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not raw:
        return None
    return Path(raw)


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    path = touched_path(event)
    if path is None:
        return 0

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0

    violations: list[str] = []
    for rule in RULES:
        if not rule.applies(path):
            continue
        for number, line in offending_lines(text, rule):
            violations.append(f"{rule.id}: {rule.message}\n  {path}:{number}\n    {line}")

    if not violations:
        return 0

    header = f"Blocked: {len(violations)} rule violation(s) in {path.name}."
    body = "\n\n".join(violations)
    footer = "See .claude/docs/design-pattern.md. Fix these before continuing."
    print(f"{header}\n\n{body}\n\n{footer}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
