#!/usr/bin/env python3
"""Keep a product in step with the Template it was cut from.

SessionStart: fetch the Template and say how many of its commits this repository
has not taken yet. `status` prints the same as JSON; `apply` replays the
Template's diff since the last sync onto the working tree and records the new
sync point in `.claude/template.json`; `mark <sha>` records it by hand after a
conflict. `/template-sync` is the skill that drives it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

CONFIG: Path = Path(".claude") / "template.json"
REMOTE: str = "template"
FETCH_EVERY: int = 6 * 60 * 60
FETCH_TIMEOUT: int = 15


def git(root: Path, *args: str, timeout: int = 10) -> str | None:
    try:
        done: subprocess.CompletedProcess[str] = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def project_root() -> Path:
    env: str | None = os.environ.get("CLAUDE_PROJECT_DIR")
    start: Path = Path(env) if env else Path.cwd()
    top: str | None = git(start, "rev-parse", "--show-toplevel")
    return Path(top) if top else start


def normalise(url: str) -> str:
    url = url.strip().rstrip("/").removesuffix(".git").lower()
    for prefix in ("git@github.com:", "ssh://git@github.com/"):
        if url.startswith(prefix):
            url = "https://github.com/" + url[len(prefix) :]
    return url


def load_config(root: Path) -> dict[str, str | None] | None:
    try:
        data: dict[str, str | None] = json.loads((root / CONFIG).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if data.get("repository") else None


def save_config(root: Path, config: dict[str, str | None]) -> None:
    (root / CONFIG).write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def is_the_template(root: Path, repository: str) -> bool:
    origin: str | None = git(root, "remote", "get-url", "origin")
    return origin is not None and normalise(origin) == normalise(repository)


def ensure_remote(root: Path, repository: str) -> None:
    current: str | None = git(root, "remote", "get-url", REMOTE)
    if current is None:
        git(root, "remote", "add", REMOTE, repository)
    elif normalise(current) != normalise(repository):
        git(root, "remote", "set-url", REMOTE, repository)


def fetch(root: Path, branch: str, force: bool) -> bool:
    stamp: Path = root / ".git" / "template-sync-fetched"
    fresh: bool = stamp.exists() and time.time() - stamp.stat().st_mtime < FETCH_EVERY
    if fresh and not force:
        return True
    fetched: str | None = git(
        root, "fetch", "--quiet", "--no-tags", REMOTE, branch, timeout=FETCH_TIMEOUT
    )
    if fetched is None:
        return False
    stamp.touch()
    return True


def baseline(root: Path, config: dict[str, str | None], upstream: str) -> str | None:
    synced: str | None = config.get("synced")
    if synced and git(root, "cat-file", "-e", f"{synced}^{{commit}}") is not None:
        return synced
    shared: str | None = git(root, "merge-base", "HEAD", upstream)
    if shared:
        return shared
    roots: str | None = git(root, "rev-list", "--max-parents=0", "HEAD")
    if not roots:
        return None
    first_tree: str | None = git(root, "rev-parse", f"{roots.splitlines()[-1]}^{{tree}}")
    listing: str | None = git(root, "log", "--format=%H %T", upstream)
    for line in (listing or "").splitlines():
        commit, tree = line.split()
        if tree == first_tree:
            return commit
    return None


@dataclass(frozen=True)
class State:
    reachable: bool
    upstream: str | None
    baseline: str | None
    behind: list[str]


def status(root: Path, force_fetch: bool) -> State | None:
    config: dict[str, str | None] | None = load_config(root)
    if config is None or is_the_template(root, str(config["repository"])):
        return None
    branch: str = config.get("branch") or "main"
    ensure_remote(root, str(config["repository"]))
    reachable: bool = fetch(root, branch, force_fetch)
    upstream: str = f"{REMOTE}/{branch}"
    head: str | None = git(root, "rev-parse", upstream)
    if head is None:
        return State(reachable, None, None, [])
    base: str | None = baseline(root, config, upstream)
    if base is None:
        return State(reachable, head, None, [])
    subjects: str = git(root, "log", "--format=%h %s", f"{base}..{head}") or ""
    return State(reachable, head, base, [line for line in subjects.splitlines() if line])


def mark(root: Path, commit: str) -> int:
    resolved: str | None = git(root, "rev-parse", "--verify", f"{commit}^{{commit}}")
    config: dict[str, str | None] | None = load_config(root)
    if resolved is None or config is None:
        print(f"Not a commit, or no {CONFIG}: {commit}", file=sys.stderr)
        return 1
    config["synced"] = resolved
    save_config(root, config)
    print(f"Recorded the Template at {resolved[:9]} as taken.")
    return 0


def apply(root: Path) -> int:
    if git(root, "status", "--porcelain") != "":
        print("The working tree is not clean. Commit or stash first.", file=sys.stderr)
        return 1
    state: State | None = status(root, force_fetch=True)
    if state is None:
        print(f"This is the Template itself, or {CONFIG} is missing.")
        return 1
    if state.upstream is None or state.baseline is None:
        print("Cannot tell which Template commit this repository last took.", file=sys.stderr)
        return 1
    if not state.behind:
        print("Already in step with the Template.")
        return 0
    diff: subprocess.CompletedProcess[bytes] = subprocess.run(
        [
            "git",
            "diff",
            "--binary",
            state.baseline,
            state.upstream,
            "--",
            ".",
            f":(exclude){CONFIG}",
        ],
        cwd=root,
        capture_output=True,
    )
    applied: subprocess.CompletedProcess[bytes] = subprocess.run(
        ["git", "apply", "--3way", "--index", "--whitespace=nowarn"],
        cwd=root,
        input=diff.stdout,
        capture_output=True,
    )
    sys.stdout.write(applied.stdout.decode(errors="replace"))
    sys.stderr.write(applied.stderr.decode(errors="replace"))
    if applied.returncode != 0:
        print(
            "Some changes conflict. Resolve them, `git add` the files, then run:\n"
            f"  python3 .claude/hooks/template-sync.py mark {state.upstream}"
        )
        return 2
    mark(root, state.upstream)
    git(root, "add", str(CONFIG))
    print(f"Took {len(state.behind)} Template commit(s).")
    return 0


def announce(root: Path) -> int:
    state: State | None = status(root, force_fetch=False)
    if state is None or state.upstream is None:
        return 0
    if state.baseline is None:
        print(
            "[template-sync] Cannot tell which Template commit this repository was cut "
            "from. Run /template-sync to set the starting point."
        )
        return 0
    if not state.behind:
        return 0
    lines: list[str] = [
        f"[template-sync] The Template has {len(state.behind)} commit(s) this repository "
        "has not taken. Run /template-sync to bring them in:"
    ]
    lines += [f"  {line}" for line in state.behind[:5]]
    if len(state.behind) > 5:
        lines.append(f"  … and {len(state.behind) - 5} more")
    print("\n".join(lines))
    return 0


def main(argv: list[str]) -> int:
    if os.environ.get("CLAUDE_TEMPLATE_SYNC_OFF") == "1":
        return 0
    root: Path = project_root()
    command: str = argv[1] if len(argv) > 1 else "announce"
    if command == "status":
        state: State | None = status(root, force_fetch=True)
        print(json.dumps(asdict(state) if state else None, indent=2))
        return 0
    if command == "apply":
        return apply(root)
    if command == "mark" and len(argv) > 2:
        return mark(root, argv[2])
    return announce(root)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
