#!/usr/bin/env python3
"""The session hooks, tested against a fabricated HOME and a real live process.

Run by CI beside `compileall`, and by hand. Nothing here touches the machine's
real registry: HOME and XDG_RUNTIME_DIR are pointed at a temporary directory,
and the "peer" is a real `sleep` this test starts and kills, so liveness is
exercised against a genuine /proc entry rather than a mock.

The silence assertions are the ones that keep the feature alive. A hook that
prints on every prompt gets deleted, and then none of the rest of this matters.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HOOKS = Path(__file__).resolve().parent
FAILED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'}  {name}{'' if ok else '  <- ' + detail}")
    if not ok:
        FAILED.append(name)


def run(hook: str, event: dict, home: Path) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "HOME": str(home),
        "XDG_RUNTIME_DIR": str(home / "run"),
        "CLAUDE_PROJECT_DIR": str(HOOKS.parents[1]),
    }
    env.pop("CLAUDE_SESSIONS_OFF", None)
    return subprocess.run(
        [sys.executable, str(HOOKS / hook)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def proc_start(pid: int) -> str:
    stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    return stat[stat.rindex(")") + 1 :].split()[19]


def pid_domain() -> str:
    machine = Path("/etc/machine-id").read_text(encoding="utf-8").strip()
    return f"linux:{machine}:{os.readlink('/proc/self/ns/pid')}"


def build_home(root: Path, peer_pid: int, peer_id: str, peer_name: str) -> Path:
    home = root / "home"
    (home / ".claude" / "sessions").mkdir(parents=True)
    (home / ".claude" / "plans").mkdir(parents=True)
    (home / ".claude" / "file-history" / peer_id).mkdir(parents=True)
    (home / "run").mkdir(parents=True)
    (home / ".claude" / "sessions" / f"{peer_pid}.json").write_text(
        json.dumps(
            {
                "pid": peer_pid,
                "sessionId": peer_id,
                "cwd": str(root / "tree"),
                "procStart": proc_start(peer_pid),
                "pidDomain": pid_domain(),
                "name": peer_name,
                "status": "busy",
                "updatedAt": time.time() * 1000,
            }
        )
    )
    return home


def main() -> int:
    sys.path.insert(0, str(HOOKS))
    peer_id = "11111111-2222-3333-4444-555555555555"
    peer_name = "the-other-session"
    me = "99999999-8888-7777-6666-555555555555"

    root = Path(tempfile.mkdtemp(prefix="session-hooks-"))
    peer = subprocess.Popen(["sleep", "120"])
    try:
        home = build_home(root, peer.pid, peer_id, peer_name)
        os.environ["HOME"] = str(home)
        os.environ["XDG_RUNTIME_DIR"] = str(home / "run")
        for name in [n for n in list(sys.modules) if n == "session_registry"]:
            del sys.modules[name]
        import session_registry as registry

        print("liveness")
        real = json.loads((home / ".claude" / "sessions" / f"{peer.pid}.json").read_text())
        check("a running process is live", registry.is_live(real))
        check("PID reuse is caught", not registry.is_live({**real, "procStart": "1"}))
        check(
            "another machine is caught",
            not registry.is_live({**real, "pidDomain": "linux:deadbeef:pid:[1]"}),
        )
        check("a dead pid is not live", not registry.is_live({**real, "pid": 999_999}))

        print("paths")
        check(
            "the same relative path in two worktrees is two files",
            registry.path_key("/a/app/x.py") != registry.path_key("/a/app-two/x.py"),
        )

        print("session-start")
        empty = run(
            "session-start.py",
            {"session_id": me, "cwd": str(root), "hook_event_name": "SessionStart"},
            root / "empty-home",
        )
        check("says nothing when nobody else is live", empty.stdout == "", repr(empty.stdout))
        check("exits 0 with no registry at all", empty.returncode == 0, empty.stderr)

        started = run(
            "session-start.py",
            {"session_id": me, "cwd": str(root), "hook_event_name": "SessionStart"},
            home,
        )
        check("names the live peer", peer_name in started.stdout, repr(started.stdout))
        check("stays within twelve lines", len(started.stdout.splitlines()) <= 12)

        print("session-peers  (the silence contract)")
        prompt = {
            "session_id": me,
            "cwd": str(root),
            "prompt": "add a thing",
            "hook_event_name": "UserPromptSubmit",
        }
        spoke = [bool(run("session-peers.py", prompt, home).stdout.strip()) for _ in range(5)]
        check("exactly one of five identical prompts speaks", sum(spoke) == 1, str(spoke))
        check("the first one is the one that speaks", spoke[0] is True, str(spoke))

        print("file-conflict-warn")
        target = root / "tree" / "shared.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x = 1\n")
        key = registry.path_key(target)
        (home / ".claude" / "file-history" / peer_id / f"{key}@v1").write_text("x = 0\n")

        conflict = run(
            "file-conflict-warn.py",
            {
                "session_id": me,
                "cwd": str(root),
                "tool_name": "Edit",
                "tool_input": {"file_path": str(target)},
                "hook_event_name": "PreToolUse",
            },
            home,
        )
        check("warns when a live peer holds the file", peer_name in conflict.stdout, repr(conflict.stdout))
        check("the warning is valid JSON", bool(json.loads(conflict.stdout or "{}")))
        check(
            "the warning does not block the edit",
            "permissionDecision" not in conflict.stdout,
        )

        mine = run(
            "file-conflict-warn.py",
            {
                "session_id": peer_id,
                "cwd": str(root),
                "tool_input": {"file_path": str(target)},
                "hook_event_name": "PreToolUse",
            },
            home,
        )
        check("a session never conflicts with itself", mine.stdout == "", repr(mine.stdout))

        # The harness keys history by the string the tool was handed. When that
        # string went through a symlink -- /tmp on macOS, a symlinked home --
        # resolving before looking up would silently never match.
        link = root / "linked"
        link.symlink_to(root / "tree")
        through = link / "only-through-the-link.py"
        (home / ".claude" / "file-history" / peer_id / f"{registry.path_key(through)}@v1").write_text("")
        via_link = run(
            "file-conflict-warn.py",
            {
                "session_id": me,
                "cwd": str(root),
                "tool_input": {"file_path": str(through)},
                "hook_event_name": "PreToolUse",
            },
            home,
        )
        check("a path recorded through a symlink still matches", peer_name in via_link.stdout, repr(via_link.stdout))

        elsewhere = run(
            "file-conflict-warn.py",
            {
                "session_id": me,
                "cwd": str(root),
                "tool_input": {"file_path": str(root / "tree-two" / "shared.py")},
                "hook_event_name": "PreToolUse",
            },
            home,
        )
        check("the same name in another worktree is not a conflict", elsewhere.stdout == "")

        plan = home / ".claude" / "plans" / "some-plan.md"
        plan.write_text("# plan\n")
        (home / ".claude" / "file-history" / peer_id / f"{registry.path_key(plan)}@v1").write_text("")
        exempted = run(
            "file-conflict-warn.py",
            {
                "session_id": me,
                "cwd": str(root),
                "tool_input": {"file_path": str(plan)},
                "hook_event_name": "PreToolUse",
            },
            home,
        )
        check("plan documents are exempt", exempted.stdout == "", repr(exempted.stdout))
        check("a peer's plan is still discoverable", registry.plan_for(peer_id) == plan)

        print("resource-claim")
        gate = {
            "session_id": peer_id,
            "cwd": str(root),
            "tool_use_id": "toolu_peer",
            "tool_input": {"command": "docker compose exec backend pytest"},
            "hook_event_name": "PreToolUse",
        }
        first = run("resource-claim.py", gate, home)
        check("the first session to take a resource is not warned", first.stdout == "")

        second = run("resource-claim.py", {**gate, "session_id": me, "tool_use_id": "toolu_me"}, home)
        check("the second session is told who has it", peer_name in second.stdout, repr(second.stdout))
        check("it names the test database", "test database" in second.stdout)

        run(
            "resource-claim.py",
            {**gate, "hook_event_name": "PostToolUse", "tool_output": ""},
            home,
        )
        after = run("resource-claim.py", {**gate, "session_id": me, "tool_use_id": "toolu_me2"}, home)
        check("a released resource stops warning", after.stdout == "", repr(after.stdout))

        held = {
            "session_id": me,
            "cwd": str(root),
            "tool_use_id": "t",
            "tool_input": {"command": "docker compose up"},
            "hook_event_name": "PreToolUse",
        }
        run("resource-claim.py", {**held, "session_id": peer_id}, home)
        peer.kill()
        peer.wait()
        dead = run("resource-claim.py", held, home)
        check("a dead holder blocks nobody", dead.stdout == "", repr(dead.stdout))

        print("bad input")
        for hook in (
            "session-start.py",
            "session-peers.py",
            "file-conflict-warn.py",
            "resource-claim.py",
        ):
            broken = subprocess.run(
                [sys.executable, str(HOOKS / hook)],
                input='{"session_id": "x", ',
                capture_output=True,
                text=True,
                env={**os.environ, "HOME": str(home), "XDG_RUNTIME_DIR": str(home / "run")},
                timeout=30,
            )
            check(f"{hook} survives truncated JSON", broken.returncode == 0 and not broken.stderr)

        (home / "run" / "claude-sessions" / f"{me}.json").write_text("")
        blank = run("session-peers.py", prompt, home)
        check("an empty sidecar is survivable", blank.returncode == 0, blank.stderr)
        (home / "run" / "claude-sessions" / f"{me}.json").write_text("null")
        null = run("session-peers.py", prompt, home)
        check("a null sidecar is survivable", null.returncode == 0, null.stderr)

        off = subprocess.run(
            [sys.executable, str(HOOKS / "session-start.py")],
            input=json.dumps({"session_id": me, "cwd": str(root)}),
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "HOME": str(home),
                "XDG_RUNTIME_DIR": str(home / "run"),
                "CLAUDE_SESSIONS_OFF": "1",
            },
            timeout=30,
        )
        check("CLAUDE_SESSIONS_OFF silences everything", off.stdout == "" and off.returncode == 0)
    finally:
        if peer.poll() is None:
            peer.kill()
            peer.wait()
        shutil.rmtree(root, ignore_errors=True)

    print()
    if FAILED:
        print(f"{len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    print("all session hook checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
