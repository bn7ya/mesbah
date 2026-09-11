#!/usr/bin/env python3
"""Shared by the session hooks: who else is live, and what are they holding.

Session awareness: a session declares itself and reads the others. Almost none of that
needs storing, because the harness already keeps most of it:

  ~/.claude/sessions/<pid>.json          one document per live session
  ~/.claude/file-history/<sid>/<hash>@vN every file that session edited
  ~/.claude/plans/<slug>.md              the plan documents, all projects mixed

So this module writes five fields the harness has no idea about -- the worktree,
the branch, the issue, what the session was last asked to do, and its own
notification bookkeeping -- and derives everything else at read time.

Liveness is `pidDomain` plus field 22 of /proc/<pid>/stat, never a heartbeat. A
heartbeat would declare a session idle overnight to be dead, which is the worst
failure available: silence exactly when a warning was due. `procStart` also rules
out PID reuse, which `os.kill(pid, 0)` alone cannot.

Sidecars live in the runtime directory, not in the repository and not in .git.
The pain this addresses -- two Docker gates on one machine, a deadlocked test
database -- is machine-scoped, not repository-scoped, and tmpfs means a reboot
reaps the whole registry correctly and for free. Presence data that outlives its
process is a lie.

One writer per file, always: the session the file describes. Readers never write
to a peer's file, so nothing here needs a lock.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

CLAUDE_HOME = Path.home() / ".claude"
HARNESS_SESSIONS = CLAUDE_HOME / "sessions"
FILE_HISTORY = CLAUDE_HOME / "file-history"
PLANS = CLAUDE_HOME / "plans"

# A file one session edited this long ago is history, not a conflict.
CONFLICT_WINDOW = 30 * 60
# The live set is re-announced at most this often, per kind of change.
NOTIFY_INTERVAL = 10 * 60
# A sidecar no live session backs is deleted once it is this old.
REAP_AFTER = 24 * 60 * 60

BRANCH_ISSUE = re.compile(r"^(?:feat|fix|docs|chore|refactor)/(\d+)-")
SAFE_RESOURCE = re.compile(r"[^A-Za-z0-9._:-]+")


def disabled() -> bool:
    """One environment variable turns the whole feature off."""
    return os.environ.get("CLAUDE_SESSIONS_OFF") == "1"


def project_root() -> Path:
    root = os.environ.get("CLAUDE_PROJECT_DIR")
    if root:
        return Path(root)
    return Path(__file__).resolve().parents[2]


# ------------------------------------------------------------------ locations


def doc_dir() -> Path:
    """Where sidecars live. tmpfs when the session has a runtime directory."""
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    base = Path(runtime) if runtime else Path.home() / ".cache"
    path = base / "claude-sessions"
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    return path


def claims_dir() -> Path:
    path = doc_dir() / "claims"
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    return path


# -------------------------------------------------------------------- reading


def load_json(path: Path) -> dict | None:
    """Every read is guarded: a foreign or truncated file must never raise."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def harness_docs() -> list[dict]:
    try:
        entries = sorted(HARNESS_SESSIONS.glob("*.json"))
    except OSError:
        return []
    return [doc for doc in (load_json(entry) for entry in entries) if doc]


def proc_start(pid: int) -> str | None:
    """Field 22 of /proc/<pid>/stat -- the process's start time in jiffies.

    The command name is field 2 and may itself contain spaces and brackets, so
    the fields are counted from after its closing parenthesis: field 3 (state)
    is the first token there, which puts field 22 at index 19.
    """
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        tail = stat[stat.rindex(")") + 1 :].split()
    except ValueError:
        return None
    return tail[19] if len(tail) > 19 else None


def pid_domain() -> str:
    """This machine and this PID namespace, in the harness's own format."""
    try:
        machine = Path("/etc/machine-id").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        machine = "unknown"
    try:
        namespace = os.readlink("/proc/self/ns/pid")
    except OSError:
        namespace = "pid:[0]"
    return f"linux:{machine}:{namespace}"


def is_live(doc: dict) -> bool:
    """A session is live if its process is still the process it claims."""
    pid = doc.get("pid")
    started = doc.get("procStart")
    domain = doc.get("pidDomain")
    if not isinstance(pid, int) or not started or not domain:
        return False
    if domain != pid_domain():
        return False
    return proc_start(pid) == str(started)


# --------------------------------------------------------------- the sidecar


def sidecar_path(session_id: str) -> Path:
    return doc_dir() / f"{session_id}.json"


def read_sidecar(session_id: str) -> dict:
    return load_json(sidecar_path(session_id)) or {}


def write_sidecar(session_id: str, **fields: object) -> dict:
    """Merge fields into my own document. Only I ever write this file."""
    doc = read_sidecar(session_id)
    doc.update(fields)
    doc["session_id"] = session_id
    doc["updated_at"] = time.time()
    write_atomic(sidecar_path(session_id), doc)
    return doc


def write_atomic(path: Path, doc: dict) -> None:
    """mkstemp in the same directory, fsync, replace. No reader sees a torn file."""
    handle, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(doc, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass


# ------------------------------------------------------------------ deriving


def git_facts(cwd: str | Path) -> tuple[str | None, str | None]:
    """The worktree root and branch for a directory, or (None, None)."""

    def ask(*args: str) -> str | None:
        try:
            done = subprocess.run(
                ("git", "-C", str(cwd), *args),
                capture_output=True,
                text=True,
                timeout=2,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        out = done.stdout.strip()
        return out if done.returncode == 0 and out else None

    # --path-format=absolute matters: from the main worktree git answers the
    # bare string ".git", and from a linked one an absolute path.
    return ask("rev-parse", "--path-format=absolute", "--show-toplevel"), ask(
        "rev-parse", "--abbrev-ref", "HEAD"
    )


def issue_of(branch: str | None) -> int | None:
    match = BRANCH_ISSUE.match(branch or "")
    return int(match.group(1)) if match else None


def history_keys(session_id: str) -> dict[str, float]:
    """Every file-history key for a session, mapped to its newest mtime."""
    keys: dict[str, float] = {}
    try:
        entries = list((FILE_HISTORY / session_id).iterdir())
    except OSError:
        return keys
    for entry in entries:
        key = entry.name.split("@", 1)[0]
        try:
            when = entry.stat().st_mtime
        except OSError:
            continue
        if when > keys.get(key, 0.0):
            keys[key] = when
    return keys


def path_key(path: str | Path) -> str:
    """The harness keys file history by sha256 of the absolute path, first 16."""
    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16]


def plan_for(session_id: str) -> Path | None:
    """The session's plan document: its file history intersected with the plans."""
    keys = history_keys(session_id)
    if not keys:
        return None
    try:
        plans = list(PLANS.glob("*.md"))
    except OSError:
        return None
    found: list[tuple[float, Path]] = []
    for plan in plans:
        when = keys.get(path_key(plan))
        if when is not None:
            found.append((when, plan))
    if not found:
        return None
    return max(found)[1]


def editors_of(path: str | Path) -> dict[str, float]:
    """Session ids that have edited this exact absolute path, and when.

    Absolute, never repository-relative: two worktrees editing the same relative
    path are editing two different files and are not in conflict.

    Both the path as given and its resolved form are looked up. The harness keys
    file history by the string the tool was handed, so on a machine where the
    tree sits behind a symlink -- /tmp on macOS, a symlinked home -- resolving
    first would silently never match, and the warning would never fire.
    """
    given = Path(path)
    keys = {path_key(given)}
    try:
        keys.add(path_key(given.resolve()))
    except OSError:
        pass
    editors: dict[str, float] = {}
    try:
        matches = [entry for key in keys for entry in FILE_HISTORY.glob(f"*/{key}@v*")]
    except OSError:
        return editors
    for entry in matches:
        try:
            when = entry.stat().st_mtime
        except OSError:
            continue
        session_id = entry.parent.name
        if when > editors.get(session_id, 0.0):
            editors[session_id] = when
    return editors


# ---------------------------------------------------------------------- peers


@dataclass(frozen=True)
class Peer:
    session_id: str
    pid: int
    name: str
    status: str
    cwd: str
    worktree: str | None
    branch: str | None
    issue: int | None
    intent: str | None
    plan: Path | None
    updated_at: float

    @property
    def label(self) -> str:
        return self.name or self.session_id[:8]


def peers(session_id: str) -> list[Peer]:
    """Every live session except me, enriched with what it told us about itself."""
    found: list[Peer] = []
    for doc in harness_docs():
        peer_id = doc.get("sessionId")
        if not peer_id or peer_id == session_id or not is_live(doc):
            continue
        side = read_sidecar(peer_id)
        found.append(
            Peer(
                session_id=peer_id,
                pid=int(doc.get("pid") or 0),
                name=str(doc.get("name") or ""),
                status=str(doc.get("status") or "unknown"),
                cwd=str(doc.get("cwd") or ""),
                worktree=side.get("worktree") or None,
                branch=side.get("branch") or None,
                issue=side.get("issue"),
                intent=side.get("intent") or None,
                plan=plan_for(peer_id),
                updated_at=float(doc.get("updatedAt") or 0) / 1000.0,
            )
        )
    return found


def reap() -> None:
    """Delete sidecars and claims no live session backs. SessionStart only."""
    alive = {doc.get("sessionId") for doc in harness_docs() if is_live(doc)}
    now = time.time()
    for directory, split in ((doc_dir(), False), (claims_dir(), True)):
        try:
            entries = list(directory.glob("*.json"))
        except OSError:
            continue
        for entry in entries:
            owner = entry.stem.split("@", 1)[1] if split and "@" in entry.stem else entry.stem
            if owner in alive:
                continue
            try:
                if split or now - entry.stat().st_mtime > REAP_AFTER:
                    entry.unlink()
            except OSError:
                pass


# --------------------------------------------------------------------- claims


def resource_name(raw: str) -> str:
    return SAFE_RESOURCE.sub("-", raw)[:60]


def claim(resource: str, session_id: str, detail: str, tool_use_id: str = "") -> None:
    """Announce that I am using a shared resource. This is not a lease.

    The file is named for the resource *and* the session, so every claim still
    has exactly one writer and no two sessions ever contend for the same file.
    Nothing waits on a claim, so a holder that dies cannot block anybody -- it
    simply stops being live, and `holders()` stops returning it.
    """
    path = claims_dir() / f"{resource_name(resource)}@{session_id}.json"
    write_atomic(
        path,
        {
            "resource": resource,
            "session_id": session_id,
            "detail": detail,
            "tool_use_id": tool_use_id,
            "at": time.time(),
        },
    )


def release(resource: str, session_id: str, tool_use_id: str = "") -> None:
    """Drop my claim -- but not one a second, still-running call of mine holds."""
    path = claims_dir() / f"{resource_name(resource)}@{session_id}.json"
    held = load_json(path)
    if held and tool_use_id and held.get("tool_use_id") not in ("", tool_use_id):
        return
    try:
        path.unlink()
    except OSError:
        pass


def my_claims(session_id: str, tool_use_id: str) -> list[str]:
    """The resources this exact tool call announced."""
    try:
        entries = list(claims_dir().glob(f"*@{session_id}.json"))
    except OSError:
        return []
    out = []
    for entry in entries:
        held = load_json(entry)
        if held and held.get("tool_use_id") == tool_use_id:
            out.append(str(held.get("resource") or ""))
    return [name for name in out if name]


def muted(session_id: str) -> bool:
    """`/sessions mute` writes this into my own document."""
    until = read_sidecar(session_id).get("mute_until")
    return isinstance(until, (int, float)) and time.time() < until


def holders(resource: str, session_id: str) -> list[dict]:
    """Live sessions other than me that have announced this resource."""
    alive = {doc.get("sessionId"): doc for doc in harness_docs() if is_live(doc)}
    out: list[dict] = []
    try:
        entries = sorted(claims_dir().glob(f"{resource_name(resource)}@*.json"))
    except OSError:
        return out
    for entry in entries:
        held = load_json(entry)
        if not held:
            continue
        owner = held.get("session_id")
        if not owner or owner == session_id or owner not in alive:
            continue
        held["name"] = alive[owner].get("name") or str(owner)[:8]
        held["cwd"] = alive[owner].get("cwd") or ""
        out.append(held)
    return out


# -------------------------------------------------------------------- writing


def ago(seconds: float) -> str:
    if seconds < 90:
        return "just now"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    return f"{hours}h ago" if hours < 48 else f"{hours // 24}d ago"


def peer_line(peer: Peer, root: Path | None) -> str:
    where = peer.worktree or peer.cwd
    if root is not None and where == str(root):
        where = "this worktree"
    else:
        where = Path(where).name if where else "unknown"
    bits = [f"{peer.label} ({peer.status})", where]
    if peer.branch:
        bits.append(peer.branch)
    if peer.intent:
        bits.append(f"“{peer.intent}”")
    return "  - " + " · ".join(bits)


def render(found: list[Peer], root: Path | None, limit: int = 5) -> str:
    """The only place peer text is formatted, so the caps live in one place."""
    if not found:
        return ""
    ordered = sorted(
        found,
        key=lambda peer: (
            (peer.worktree or peer.cwd) != str(root) if root else True,
            -peer.updated_at,
        ),
    )
    lines = [f"[sessions] {len(ordered)} other Claude session(s) live on this machine:"]
    for peer in ordered[:limit]:
        lines.append(peer_line(peer, root))
        if peer.plan is not None:
            lines.append(f"      plan: {peer.plan}")
    if len(ordered) > limit:
        lines.append(f"  ... and {len(ordered) - limit} more")
    lines.append("  Coordinate with `/sessions` before editing what they hold.")
    return "\n".join(lines)


# ------------------------------------------------------------------------ cli


def current_session_id() -> str:
    """The session this process is running inside, walked up the parent chain.

    A hook is told its session id on stdin, but the command line is not, and
    `--list` that counted the caller as a peer would be worse than useless.
    """
    owners = {doc.get("pid"): doc.get("sessionId") for doc in harness_docs()}
    pid = os.getpid()
    for _ in range(24):
        if pid in owners:
            return str(owners[pid] or "")
        try:
            status = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            break
        match = re.search(r"^PPid:\s+(\d+)$", status, re.MULTILINE)
        if not match:
            break
        pid = int(match.group(1))
        if pid <= 1:
            break
    return os.environ.get("CLAUDE_SESSION_ID", "")


def main(argv: list[str]) -> int:
    """`--list` for a person, `--json` for a test. The skill uses both."""
    mine = current_session_id()

    if "--mute" in argv:
        index = argv.index("--mute")
        minutes = float(argv[index + 1]) if len(argv) > index + 1 else 30.0
        if not mine:
            print("Not running inside a session, so there is nothing to mute.")
            return 1
        write_sidecar(mine, mute_until=time.time() + minutes * 60)
        print(f"Session notices are muted for {minutes:g} minutes.")
        return 0

    found = peers(mine)
    if "--json" in argv:
        print(
            json.dumps(
                [
                    {
                        **{
                            key: getattr(peer, key)
                            for key in (
                                "session_id",
                                "pid",
                                "name",
                                "status",
                                "cwd",
                                "worktree",
                                "branch",
                                "issue",
                                "intent",
                            )
                        },
                        "plan": str(peer.plan) if peer.plan else None,
                    }
                    for peer in found
                ],
                indent=2,
            )
        )
        return 0
    if not found:
        print("No other Claude session is live on this machine.")
        return 0
    root, _ = git_facts(Path.cwd())
    print(render(found, Path(root) if root else None, limit=20))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
