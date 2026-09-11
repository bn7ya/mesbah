#!/usr/bin/env python3
"""PreToolUse and PostToolUse on Bash: announce the machine's shared resources.

Session awareness. Two sessions running the Docker gate at once load the machine and time
each other out; a backgrounded pytest in one session holds the test database the
other one needs. Neither session can see the other doing it.

So a command that is about to take one of those announces it, and a session
about to start the same thing is told who already has it. This is an
announcement, never a lease: nothing waits, nothing is blocked, and a holder
that dies simply stops being live. A lock here would be worse than the collision
-- a session waiting forever on a lease held by a dead process.

`compose:<project>` is the sharpest of the three. Every worktree's
docker-compose.django.yml declares the same project name, so a second `docker compose up`
from a different worktree does not start a second stack: it reuses and mutates the first one.
That is the real mechanism behind the deadlocked test database, and this makes
it visible at the moment it is about to happen.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import session_registry as registry

COMPOSE = re.compile(r"\bdocker[ -]compose\b")
COMPOSE_PROJECT = re.compile(r"(?:-p|--project-name)[= ]+([\w.-]+)")
TESTDB = re.compile(r"\bpytest\b|\bmanage\.py\s+test\b")
GATE = re.compile(
    r"\bng\s+(?:test|build|lint)\b|\bnpm\s+(?:run|test)\b|\bruff\b|\bplaywright\b|"
    r"\bmanage\.py\s+(?:migrate|makemigrations|spectacular)\b"
)

RESOURCE_LABEL = {
    "gate": "the gate",
    "testdb": "the test database",
}


def compose_project(cwd: str) -> str:
    """The project name a compose command in this directory would use."""
    root, _ = registry.git_facts(cwd)
    base = Path(root) if root else Path(cwd)
    for name in ("compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.django.yml"):
        try:
            for line in (base / name).read_text(encoding="utf-8").splitlines():
                if line.startswith("name:"):
                    return line.split(":", 1)[1].strip().strip("\"'")
        except (OSError, UnicodeDecodeError):
            continue
    return base.name


def resources_for(command: str, cwd: str) -> list[str]:
    found: list[str] = []
    if TESTDB.search(command):
        found.append("testdb")
    if GATE.search(command) or TESTDB.search(command):
        found.append("gate")
    if COMPOSE.search(command):
        named = COMPOSE_PROJECT.search(command)
        found.append(f"compose:{named.group(1) if named else compose_project(cwd)}")
    return found


def describe(resource: str) -> str:
    if resource.startswith("compose:"):
        return f"the compose project `{resource.split(':', 1)[1]}`"
    return RESOURCE_LABEL.get(resource, resource)


def main() -> int:
    if registry.disabled():
        return 0

    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    session_id = event.get("session_id") or ""
    tool_use_id = event.get("tool_use_id") or ""
    if not session_id:
        return 0

    # Releasing is unconditional: a muted session must still let go.
    if event.get("hook_event_name") == "PostToolUse":
        for resource in registry.my_claims(session_id, tool_use_id):
            registry.release(resource, session_id, tool_use_id)
        return 0

    command = (event.get("tool_input") or {}).get("command") or ""
    cwd = event.get("cwd") or str(Path.cwd())
    resources = resources_for(command, cwd)
    if not resources:
        return 0

    lines: list[str] = []
    for resource in resources:
        for held in registry.holders(resource, session_id):
            lines.append(
                f"  {describe(resource)} — {held['name']} took it "
                f"{registry.ago(time.time() - float(held.get('at') or 0))}"
                + (f" in {Path(held['cwd']).name}" if held.get("cwd") else "")
            )
        registry.claim(resource, session_id, command[:120], tool_use_id)

    if not lines or registry.muted(session_id):
        return 0

    body = "\n".join(
        ["[sessions] Another live session is already using what this command needs:", *lines[:4]]
        + [
            "  Running it now will contend for the same machine, and for a compose "
            "project the second run mutates the first one's stack rather than "
            "starting its own. Consider waiting, or ask the user."
        ]
    )
    print(
        json.dumps(
            {
                "systemMessage": "Another session is already using this resource.",
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
