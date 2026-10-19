from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from tools.release import changelog
from tools.release.version import BACKEND, CHANGELOG, REPOSITORY, Release, ReleaseError, parse_tag

type Kind = Literal["breaking", "additive", "internal", "blocking"]
type Facts = dict[str, str]

GOLDENS: Path = BACKEND / "contracts"
PUBLIC: tuple[str, ...] = ("openapi.json", "compat.json", "cli.json")
IGNORED_KEYS: frozenset[str] = frozenset({"description", "summary", "title", "example", "examples"})
CONTRACTS_HEADING: str = "### Contracts"


@dataclass(frozen=True)
class Change:
    file: str
    kind: Kind
    what: str


@dataclass(frozen=True)
class Verdict:
    changes: tuple[Change, ...]

    @property
    def kind(self) -> str:
        kinds: set[str] = {change.kind for change in self.changes}
        for strongest in ("blocking", "breaking", "additive", "internal"):
            if strongest in kinds:
                return strongest
        return "none"

    def only_new_migrations(self) -> bool:
        return all(
            change.file == "migrations.json" and change.kind == "additive"
            for change in self.changes
            if change.kind != "internal"
        )


def facts(value: object, prefix: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(value, dict):
        yield prefix, "object"
        for key, item in value.items():
            if str(key) not in IGNORED_KEYS:
                yield from facts(item, f"{prefix}/{key}")
    elif isinstance(value, list):
        yield prefix, "array"
        if all(isinstance(item, str | int | float | bool) or item is None for item in value):
            for item in value:
                yield f"{prefix}[{json.dumps(item)}]", "item"
        else:
            for index, item in enumerate(value):
                yield from facts(item, f"{prefix}[{index}]")
    else:
        yield prefix, json.dumps(value)


def flat(value: object) -> Facts:
    return dict(facts(value))


def required_in_request(path: str) -> bool:
    return "/required[" in path and "Request/" in path


def compare_public(name: str, old: Facts, new: Facts) -> list[Change]:
    changes: list[Change] = []
    for path in sorted(old.keys() - new.keys()):
        kind: Kind = "additive" if required_in_request(path) else "breaking"
        changes.append(Change(name, kind, f"removed {path}"))
    for path in sorted(new.keys() - old.keys()):
        tightened: bool = required_in_request(path) and path.split("/required[")[0] in old
        kind = "breaking" if tightened else "additive"
        changes.append(Change(name, kind, f"added {path}"))
    for path in sorted(old.keys() & new.keys()):
        if old[path] != new[path]:
            changes.append(Change(name, "breaking", f"changed {path}: {old[path]} → {new[path]}"))
    return changes


def compare_migrations(old: object, new: object) -> list[Change]:
    before: Facts = flat(old)
    after: Facts = flat(new)
    changes: list[Change] = [
        Change("migrations.json", "blocking", f"a shipped migration is gone: {path}")
        for path in sorted(before.keys() - after.keys())
    ]
    changes += [
        Change("migrations.json", "blocking", f"a shipped migration was edited: {path}")
        for path in sorted(before.keys() & after.keys())
        if before[path] != after[path]
    ]
    changes += [
        Change("migrations.json", "additive", f"a new migration: {path}")
        for path in sorted(after.keys() - before.keys())
    ]
    return changes


def compare(old: dict[str, object], new: dict[str, object]) -> Verdict:
    changes: list[Change] = []
    for name in sorted(old.keys() | new.keys()):
        if name == "migrations.json":
            changes += compare_migrations(old.get(name, {}), new.get(name, {}))
        elif name in PUBLIC:
            changes += compare_public(name, flat(old.get(name, {})), flat(new.get(name, {})))
        elif flat(old.get(name, {})) != flat(new.get(name, {})):
            changes.append(Change(name, "internal", "changed between Mesbah's own processes"))
    return Verdict(tuple(changes))


def allowed(verdict: Verdict, before: Release, after: Release) -> str | None:
    if verdict.kind == "blocking":
        return "a shipped migration changed or disappeared; add a new migration instead"
    patch: bool = (after.major, after.minor) == (before.major, before.minor)
    if patch and not verdict.only_new_migrations():
        return f"{after.final} is a patch, and a patch may only add migrations"
    if verdict.kind == "breaking" and after.major >= 1 and after.major == before.major:
        return f"{after.final} breaks a contract, which needs {after.major + 1}.0.0"
    return None


def golden(name: str, ref: str | None) -> object:
    if ref is None:
        return json.loads((GOLDENS / name).read_text(encoding="utf-8"))
    shown: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603 - git with a ref
        ["git", "show", f"{ref}:backend/contracts/{name}"],  # noqa: S607
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=False,
    )
    return json.loads(shown.stdout) if shown.returncode == 0 else {}


def snapshots(ref: str | None) -> dict[str, object]:
    names: list[str] = sorted(path.name for path in GOLDENS.glob("*.json"))
    return {name: golden(name, ref) for name in names}


def markdown(verdict: Verdict, before: str, after: str) -> str:
    lines: list[str] = [f"# Contracts, {before} → {after}", "", f"**{verdict.kind}**", ""]
    for kind in ("blocking", "breaking", "additive", "internal"):
        listed: list[Change] = [change for change in verdict.changes if change.kind == kind]
        if listed:
            lines += [f"## {kind.capitalize()}", ""]
            lines += [f"- `{change.file}` {change.what}" for change in listed]
            lines.append("")
    if not verdict.changes:
        lines.append("Nothing a release promises changed.")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="python -m tools.release.contracts"
    )
    parser.add_argument("--previous", required=True, help="the last release's tag")
    parser.add_argument("--tag", required=True, help="the release being made")
    parser.add_argument("--out", type=Path, required=True, help="a folder for the reports")
    parser.add_argument("--report-only", action="store_true", help="say, never refuse")
    arguments: argparse.Namespace = parser.parse_args(argv)
    try:
        before: Release = parse_tag(arguments.previous)
        after: Release = parse_tag(arguments.tag)
    except ReleaseError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    verdict: Verdict = compare(snapshots(arguments.previous), snapshots(None))
    arguments.out.mkdir(parents=True, exist_ok=True)
    (arguments.out / "compare.json").write_text(
        json.dumps(
            {"kind": verdict.kind, "changes": [asdict(change) for change in verdict.changes]},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (arguments.out / "contracts-diff.md").write_text(
        markdown(verdict, before.tag, after.tag), encoding="utf-8"
    )
    print(f"{before.tag} → {after.tag}: {verdict.kind}, {len(verdict.changes)} changes")
    refusal: str | None = allowed(verdict, before, after)
    notes: changelog.Section | None = changelog.section(
        CHANGELOG.read_text(encoding="utf-8"), after.final
    )
    unexplained: bool = notes is None or CONTRACTS_HEADING not in notes.body
    if refusal is None and verdict.kind in {"breaking", "additive"} and unexplained:
        refusal = f"the changelog's {after.final} section says nothing under {CONTRACTS_HEADING}"
    if refusal is not None:
        print(f"{'note' if arguments.report_only else 'error'}: {refusal}", file=sys.stderr)
        return 0 if arguments.report_only else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
