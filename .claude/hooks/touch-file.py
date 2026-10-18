#!/usr/bin/env python3
"""Record a file edit so file-conflict-warn can match it across sessions.

Rule 28. opencode has no `~/.claude/file-history`, so the plugin records each
edit here, in the session's own sidecar. file-conflict-warn unions that with
the harness file-history, so a warning fires regardless of which harness made
the edit.
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
    raw = (event.get("tool_input") or {}).get("file_path") or event.get("path")
    if not session_id or not raw:
        return 0

    path = Path(raw)
    if not path.is_absolute():
        path = Path(event.get("cwd") or Path.cwd()) / path

    registry.touch_file(session_id, str(path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
