from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence

from tools.release.version import REPOSITORY, Release, ReleaseError, parse_tag


def tags() -> list[str]:
    listed: str = subprocess.run(  # noqa: S603 - git with fixed arguments
        ["git", "tag", "--list", "v*"],  # noqa: S607
        cwd=REPOSITORY,
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    return [line.strip() for line in listed.splitlines() if line.strip()]


def releases(names: list[str]) -> list[Release]:
    found: list[Release] = []
    for name in names:
        try:
            found.append(parse_tag(name))
        except ReleaseError:
            continue
    return sorted(found, key=lambda release: release.key)


def previous(version: Release, names: list[str]) -> Release | None:
    stable: list[Release] = [
        release
        for release in releases(names)
        if not release.is_candidate and release.key < version.as_final().key
    ]
    return stable[-1] if stable else None


def main(argv: Sequence[str] | None = None) -> int:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(prog="python -m tools.release.tags")
    commands: argparse._SubParsersAction[argparse.ArgumentParser] = parser.add_subparsers(
        dest="command", required=True
    )
    before: argparse.ArgumentParser = commands.add_parser(
        "previous", help="the last stable release before a tag, or nothing"
    )
    before.add_argument("tag")
    arguments: argparse.Namespace = parser.parse_args(argv)
    try:
        found: Release | None = previous(parse_tag(arguments.tag), tags())
    except ReleaseError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print("" if found is None else found.tag)
    return 0


if __name__ == "__main__":
    sys.exit(main())
