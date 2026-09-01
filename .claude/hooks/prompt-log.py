#!/usr/bin/env python3
"""UserPromptSubmit hook: append every submitted prompt to prompt.txt.

Claude Code delivers the event as JSON on stdin. The prompt text is in the
`prompt` field. Anything this hook writes to stdout is injected into Claude's
context, so it stays silent and communicates only through its exit code.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

LOG_NAME = "prompt.txt"


def project_root() -> Path:
    root = os.environ.get("CLAUDE_PROJECT_DIR")
    if root:
        return Path(root)
    return Path(__file__).resolve().parents[2]


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    prompt = (event.get("prompt") or "").strip()
    if not prompt:
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    session = (event.get("session_id") or "unknown")[:8]

    entry = f"[{stamp}] session={session}\n{prompt}\n\n---\n\n"

    try:
        log = project_root() / LOG_NAME
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as handle:
            handle.write(entry)
    except OSError as exc:
        # Never block a prompt because logging failed.
        print(f"prompt-log: could not write {LOG_NAME}: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
