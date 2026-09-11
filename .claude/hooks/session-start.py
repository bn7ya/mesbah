#!/usr/bin/env python3
"""SessionStart hook: tell a new session who else is live.

Session awareness. The harness knows which sessions are running; it does not know which
worktree or branch each one sits on, and it never volunteers any of it. This
writes that half down and prints the other sessions once, at the top of the
session, where it costs one paragraph and saves a collision.

Silence is the default and the common case: with no live peer this prints
nothing at all, so a single-session day pays nothing for the feature.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import session_registry as registry


def main() -> int:
    if registry.disabled():
        return 0

    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    session_id = event.get("session_id")
    if not session_id:
        return 0

    cwd = event.get("cwd") or str(Path.cwd())
    worktree, branch = registry.git_facts(cwd)

    registry.write_sidecar(
        session_id,
        cwd=cwd,
        worktree=worktree,
        branch=branch,
        issue=registry.issue_of(branch),
        started_at=time.time(),
    )

    # Once a session, never on the per-prompt path.
    registry.reap()

    found = registry.peers(session_id)
    if not found:
        return 0

    block = registry.render(found, Path(worktree) if worktree else None)
    if block:
        print(block)
    return 0


if __name__ == "__main__":
    sys.exit(main())
