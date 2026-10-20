#!/usr/bin/env python3
"""Record an opencode session as a live harness document.

Rule 28. Claude Code's harness writes one `~/.claude/sessions/<pid>.json` per
live session; that document is the thing every peer-lookup trusts, because its
`procStart` is checked against a real `/proc` entry. opencode has no such
harness, so its plugin calls this once per session, passing its own pid.

From here on the session is discoverable exactly like a Claude one: `peers`,
`holders` and `reap` all find it, and when the process exits the `/proc` check
marks it dead with no cleanup needed.
"""

from __future__ import annotations

import json
import sys
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
    pid = event.get("pid")
    if not session_id or not isinstance(pid, int):
        return 0

    cwd = event.get("cwd") or str(Path.cwd())
    name = (event.get("name") or "").strip() or f"opencode-{pid}"

    registry.register_harness(pid, session_id, cwd, name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
