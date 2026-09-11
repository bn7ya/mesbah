#!/usr/bin/env python3
"""UserPromptSubmit hook: speak only when the live set actually changed.

Session awareness. Two hooks already run on every prompt, one of which prints fifteen
lines whenever the prompt looks like work. A third talkative hook is how a
person ends up deleting all three, so this one is silent by default: it hashes
the live set into a digest, keeps the digest in its own document, and prints
nothing at all while that digest holds. A peer that merely goes on existing is
silent on the second prompt and on the two-hundredth.

Four things are worth interrupting for, and nothing else is: a session appeared,
a session we had named went away, a session moved onto our branch, or a session
walked into our worktree.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import session_registry as registry

MAX_LINES = 6


def digest_of(peers: list[registry.Peer]) -> str:
    material = sorted(
        f"{peer.session_id}|{peer.branch or ''}|{peer.worktree or peer.cwd}" for peer in peers
    )
    return hashlib.sha256("\n".join(material).encode("utf-8")).hexdigest()[:16]


def allowed(stamps: dict, kind: str, now: float) -> bool:
    last = stamps.get(kind)
    return not isinstance(last, (int, float)) or now - last >= registry.NOTIFY_INTERVAL


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
    intent = " ".join((event.get("prompt") or "").split())[:100]

    mine = registry.read_sidecar(session_id)
    notify = mine.get("notify") or {}
    seen = notify.get("seen") or {}
    stamps = notify.get("stamps") or {}

    found = registry.peers(session_id)
    digest = digest_of(found)
    now = time.time()

    lines: list[str] = []
    if digest != notify.get("digest") and not registry.muted(session_id):
        live = {peer.session_id: peer for peer in found}

        fresh = [peer for peer in found if peer.session_id not in seen]
        if fresh and allowed(stamps, "appeared", now):
            stamps["appeared"] = now
            for peer in fresh[:2]:
                where = Path(peer.worktree or peer.cwd).name or peer.cwd
                on = f" on {peer.branch}" if peer.branch else ""
                lines.append(f"[sessions] {peer.label} started in {where}{on}.")

        gone = [was for sid, was in seen.items() if sid not in live]
        if gone and allowed(stamps, "left", now):
            stamps["left"] = now
            names = ", ".join(str(was.get("label") or "a session") for was in gone[:3])
            lines.append(f"[sessions] {names} ended.")

        if branch:
            joined = [
                peer
                for peer in found
                if peer.branch == branch and seen.get(peer.session_id, {}).get("branch") != branch
            ]
            if joined and allowed(stamps, "branch", now):
                stamps["branch"] = now
                names = ", ".join(peer.label for peer in joined[:3])
                lines.append(f"[sessions] {names} is now on your branch {branch}. Pull before you commit.")

        if worktree:
            entered = [
                peer
                for peer in found
                if (peer.worktree or peer.cwd) == worktree
                and seen.get(peer.session_id, {}).get("worktree") != worktree
            ]
            if entered and allowed(stamps, "worktree", now):
                stamps["worktree"] = now
                names = ", ".join(peer.label for peer in entered[:3])
                lines.append(f"[sessions] {names} is working in this worktree. Check `/sessions` before editing.")

    registry.write_sidecar(
        session_id,
        cwd=cwd,
        worktree=worktree,
        branch=branch,
        issue=registry.issue_of(branch),
        intent=intent,
        notify={
            "digest": digest,
            "stamps": stamps,
            "seen": {
                peer.session_id: {
                    "label": peer.label,
                    "branch": peer.branch,
                    "worktree": peer.worktree or peer.cwd,
                }
                for peer in found
            },
        },
    )

    if lines:
        if len(lines) > MAX_LINES:
            lines = lines[: MAX_LINES - 1] + ["[sessions] More has changed — run `/sessions`."]
        print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
