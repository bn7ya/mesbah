#!/usr/bin/env python3
"""Stop hook: keep feature memory in sync with feature code.

Mesbah's own root CLAUDE.md says every feature directory carries a
CLAUDE.md, updated whenever the feature changes -- on both the live FastAPI
backend (backend/app/features/) and the Angular frontend
(frontend/src/app/features/), plus the Django migration target
(backend/apps/, apps/common excepted per its own CLAUDE.md). This hook
reads the session transcript, works out which feature directories were
written to this turn, and blocks the stop if any of them has a missing or
stale CLAUDE.md.

Stale means: a source file in the feature was modified during this turn but
the feature's CLAUDE.md was not.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

FEATURE_ROOTS = (
    ("frontend", "src", "app", "features"),
    ("backend", "app", "features"),   # live FastAPI backend
    ("backend", "apps"),              # Django migration target
)
IGNORED_APPS = {"common"}
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def project_root() -> Path:
    root = os.environ.get("CLAUDE_PROJECT_DIR")
    if root:
        return Path(root)
    return Path(__file__).resolve().parents[2]


def feature_dir_for(path: Path, root: Path) -> Path | None:
    """Return the feature directory a path belongs to, or None."""
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return None

    for marker in FEATURE_ROOTS:
        n = len(marker)
        # `> n + 1` and not `> n`: the path has to be *inside* a feature
        # directory. A file sitting directly in the root -- apps/__init__.py,
        # features/CLAUDE.md -- names no feature.
        if len(parts) > n + 1 and parts[:n] == marker:
            name = parts[n]
            if name in IGNORED_APPS:
                return None
            feature = root.joinpath(*marker, name)
            return feature if feature.is_dir() else None
    return None


def written_paths(transcript: Path) -> list[Path]:
    """Every file path written by a tool call recorded in the transcript."""
    paths: list[Path] = []
    try:
        lines = transcript.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return paths

    for line in lines:
        try:
            record = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue

        message = record.get("message") or {}
        content = message.get("content")
        if not isinstance(content, list):
            continue

        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            if block.get("name") not in WRITE_TOOLS:
                continue
            raw = (block.get("input") or {}).get("file_path")
            if raw:
                paths.append(Path(raw))

    return paths


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    # Do not fight an already-blocked stop.
    if event.get("stop_hook_active"):
        return 0

    transcript_raw = event.get("transcript_path")
    if not transcript_raw:
        return 0

    root = project_root()
    touched = written_paths(Path(transcript_raw).expanduser())
    if not touched:
        return 0

    features: dict[Path, bool] = {}
    for path in touched:
        feature = feature_dir_for(path, root)
        if feature is None:
            continue
        memory_written = features.get(feature, False)
        if path.name == "CLAUDE.md":
            memory_written = True
        features[feature] = memory_written

    stale = []
    for feature, memory_written in features.items():
        memory = feature / "CLAUDE.md"
        if not memory.exists():
            stale.append((feature, "missing"))
        elif not memory_written:
            stale.append((feature, "not updated"))

    if not stale:
        return 0

    lines = [
        "Feature memory is out of sync (root CLAUDE.md: every feature",
        "directory carries a CLAUDE.md).",
        "",
        "You changed these features but their CLAUDE.md was not written:",
        "",
    ]
    for feature, why in stale:
        rel = feature.relative_to(root) if feature.is_relative_to(root) else feature
        lines.append(f"  - {rel}/CLAUDE.md  ({why})")
    lines += [
        "",
        "Write or update each one, then finish. A feature's CLAUDE.md should record",
        "what the feature does, its slice counterpart on the other side (if any),",
        "its routes and endpoints, and any decision a future session would",
        "otherwise re-litigate.",
    ]

    print("\n".join(lines), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
