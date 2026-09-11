#!/usr/bin/env python3
"""PreToolUse hook: warn before editing a file a live session is holding.

Session awareness. The harness records every file each session edits, under
~/.claude/file-history/<session>/<sha256(absolute path)[:16]>@v<n>, so this hook
writes nothing and only reads: hash the path, see who else has touched it, keep
the ones whose process is still alive.

The hash is of the **absolute** path, deliberately. Two sessions editing
backend/app/features/inference/engine.py in two worktrees are editing two different
files and are not in conflict at all; comparing repository-relative paths would
invent that conflict, and a warning that is usually wrong gets switched off.

It warns and lets the edit through. One person drives both sessions and knows
things this hook does not -- put the decision where the knowledge is. Turning
the warning into a stop is one line: add
`"permissionDecision": "ask"` to hookSpecificOutput below.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import session_registry as registry


def exempt(path: Path) -> bool:
    """Files every session is expected to write, which are never a conflict."""
    parts = path.parts
    if ".claude" in parts:
        # Plans, settings, hooks, feature memory: each session writes its own,
        # and a peer's plan is in its file history precisely so we can read it.
        return True
    return path.name == "prompt.txt"


def main() -> int:
    if registry.disabled():
        return 0

    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    session_id = event.get("session_id") or ""
    if registry.muted(session_id):
        return 0

    tool_input = event.get("tool_input") or {}
    raw = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not raw:
        return 0

    path = Path(raw)
    if not path.is_absolute():
        path = Path(event.get("cwd") or Path.cwd()) / path
    if exempt(path):
        return 0

    now = time.time()
    editors = registry.editors_of(path)
    if not editors:
        return 0

    alive = {
        doc.get("sessionId"): doc for doc in registry.harness_docs() if registry.is_live(doc)
    }

    holders = []
    for editor, when in sorted(editors.items(), key=lambda item: -item[1]):
        if editor == session_id or editor not in alive:
            continue
        if now - when > registry.CONFLICT_WINDOW:
            continue
        holders.append((alive[editor], when))

    if not holders:
        return 0

    doc, when = holders[0]
    label = doc.get("name") or str(doc.get("sessionId"))[:8]
    side = registry.read_sidecar(str(doc.get("sessionId")))
    plan = registry.plan_for(str(doc.get("sessionId")))

    detail = [
        f"[sessions] {label} edited this file {registry.ago(now - when)}.",
        f"  file:   {path}",
        f"  where:  {side.get('worktree') or doc.get('cwd')}"
        + (f" · {side['branch']}" if side.get("branch") else ""),
    ]
    if side.get("intent"):
        detail.append(f"  doing:  {side['intent']}")
    if plan is not None:
        detail.append(f"  plan:   {plan}")
    detail.append(
        "  Read their plan, or message them by name with SendMessage, before you "
        "overwrite their work. The edit is not blocked."
    )
    if len(holders) > 1:
        detail.append(f"  ({len(holders) - 1} other live session(s) have this file too.)")

    body = "\n".join(detail)
    print(
        json.dumps(
            {
                "systemMessage": f"{label} edited {path.name} {registry.ago(now - when)}.",
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": body,
                },
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
