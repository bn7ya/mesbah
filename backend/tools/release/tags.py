from __future__ import annotations

import subprocess

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
