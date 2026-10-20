#!/usr/bin/env python3
"""UserPromptSubmit hook: hold feature, fix and refactor work to the git flow.

Rules 23 to 27 in CLAUDE.md say an issue comes before the first edit and the
work lands as small commits that each pass CI. A rule read once at session start
scrolls away; this hook restates it on every prompt that looks like the kind of
work it governs.

Claude Code delivers the event as JSON on stdin and injects whatever this hook
writes to stdout into the context. It is advisory — it classifies, it prints,
and it always exits 0. A prompt is never blocked.
"""

from __future__ import annotations

import json
import re
import sys

# Ordered: the first pattern to match wins. Fix before refactor before feature,
# because "fix the duplicated service" is a fix that happens to mention
# structure, and "add the missing error state" is a feature that mentions an
# error.
KINDS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "fix",
        "bug",
        re.compile(
            r"\b(fix(es|ed|ing)?|bugs?|broken|breaks?|breaking|regression|"
            r"fail(s|ed|ing|ure)?|errors?|crash(es|ed|ing)?|traceback|exception|"
            r"not working|does ?n[o']t work|is ?n[o']t working|wrong|incorrect|"
            r"misaligned|off by)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "refactor",
        "refactor",
        re.compile(
            r"\b(refactor(s|ed|ing)?|rename|extract|restructure|reorgani[sz]e|"
            r"simplify|deduplicate|clean ?up|tidy|consolidate|decouple|inline|"
            r"split .+ into|move .+ (in)?to)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "feat",
        "enhancement",
        re.compile(
            r"\b(add|creat(e|ing)|implement|build|introduce|support|enable|"
            r"new (page|endpoint|feature|slice|field|screen|app)|feature|"
            r"allow .+ to)\b",
            re.IGNORECASE,
        ),
    ),
)

# A prompt that opens like a question and never names an action is a request to
# explain, not to build. Those get no reminder.
READ_ONLY_LEAD = re.compile(
    r"^\W*(what|why|how|where|when|which|who|whose|is|are|was|were|does|do|did|"
    r"can|could|should|would|explain|describe|show|list|read|review|check|"
    r"compare|summari[sz]e|tell me|walk me|help me understand|thoughts)\b",
    re.IGNORECASE,
)

ACTION = re.compile(
    r"\b(add|create|implement|build|introduce|support|enable|fix|repair|correct|"
    r"refactor|rename|extract|restructure|simplify|split|move|remove|delete|"
    r"drop|update|change|migrate|wire|clean ?up)\b",
    re.IGNORECASE,
)

REMINDER = """\
[git-flow] This reads as {kind} work.

The issue comes before the first edit — `.claude/skills/git-flow/SKILL.md`, and
rules 23 to 27 in CLAUDE.md:

  1. `gh issue create --label {label}` — one issue per thing that works alone
  2. `git switch -c {kind}/<issue>-<slug> main` — one slice per branch
  3. run the gate — what CI runs; red is not a commit
  4. `{kind}(<scope>): <subject> (#N)`, push it, PR when the slice is done

Split the work by behaviour, never into a backend commit and then a frontend
one. Every commit must be a working application on its own.

Already building an issue for this? Stay on it. Asking rather than building?
Ignore this."""


def classify(prompt: str) -> tuple[str, str] | None:
    """Return (kind, label) for work that needs an issue, else None."""
    question = bool(READ_ONLY_LEAD.match(prompt))
    for kind, label, pattern in KINDS:
        if not pattern.search(prompt):
            continue
        # "what causes this error?" matches the fix vocabulary without asking
        # for a fix. An explicit action verb is what separates the two.
        if question and not ACTION.search(prompt):
            return None
        return kind, label
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    prompt = (event.get("prompt") or "").strip()
    if not prompt or prompt.startswith(("/", "!", "#")):
        return 0

    match = classify(prompt)
    if match is None:
        return 0

    kind, label = match
    print(REMINDER.format(kind=kind, label=label))
    return 0


if __name__ == "__main__":
    sys.exit(main())
