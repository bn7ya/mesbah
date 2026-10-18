#!/usr/bin/env python3
"""Cut a product from a throwaway Template, move the Template on, and sync."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK: Path = Path(__file__).resolve().parent / "template-sync.py"
IDENTITY: list[str] = ["-c", "user.name=t", "-c", "user.email=t@example.com"]


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *IDENTITY, *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def hook(product: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env: dict[str, str] = {**os.environ, "CLAUDE_PROJECT_DIR": str(product)}
    env.pop("CLAUDE_TEMPLATE_SYNC_OFF", None)
    return subprocess.run(
        [sys.executable, str(HOOK), *args],
        cwd=product,
        env=env,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as scratch:
        template: Path = Path(scratch) / "template"
        product: Path = Path(scratch) / "product"
        template.mkdir()
        (template / ".claude").mkdir()
        (template / "rules.md").write_text("one\n")
        (template / "README.md").write_text("Template\n")
        (template / ".claude" / "template.json").write_text(
            json.dumps({"repository": str(template), "branch": "main", "synced": None})
        )
        git(template, "init", "-q", "-b", "main")
        git(template, "add", "-A")
        git(template, "commit", "-qm", "start")

        product.mkdir()
        git(product, "init", "-q", "-b", "main")
        git(template, "archive", "HEAD", "-o", str(Path(scratch) / "t.tar"))
        subprocess.run(["tar", "xf", str(Path(scratch) / "t.tar")], cwd=product, check=True)
        git(product, "add", "-A")
        git(product, "commit", "-qm", "Initial commit")
        (product / "README.md").write_text("Product\n")
        git(product, "commit", "-qam", "name the product")

        failures: list[str] = []
        if hook(product).stdout.strip():
            failures.append("spoke while the product was in step")

        (template / "rules.md").write_text("one\ntwo\n")
        git(template, "commit", "-qam", "add rule two")
        (product / ".git" / "template-sync-fetched").unlink(missing_ok=True)

        if "1 commit(s)" not in hook(product).stdout:
            failures.append("did not announce the new Template commit")

        applied: subprocess.CompletedProcess[str] = hook(product, "apply")
        if applied.returncode != 0:
            failures.append(f"apply failed: {applied.stdout}{applied.stderr}")
        if (product / "rules.md").read_text() != "one\ntwo\n":
            failures.append("the Template change did not arrive")
        if (product / "README.md").read_text() != "Product\n":
            failures.append("the product's own change was overwritten")
        git(product, "commit", "-qm", "sync")
        (product / ".git" / "template-sync-fetched").unlink(missing_ok=True)
        if hook(product).stdout.strip():
            failures.append("still spoke after the sync")

    for failure in failures:
        print(f"FAIL: {failure}")
    print("template-sync: ok" if not failures else "template-sync: failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
