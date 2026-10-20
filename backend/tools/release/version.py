from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from tools.release import changelog

BACKEND: Path = Path(__file__).resolve().parents[2]
REPOSITORY: Path = BACKEND.parent
SOURCE: Path = BACKEND / "mesbah" / "__init__.py"
CHANGELOG: Path = REPOSITORY / "CHANGELOG.md"
SOURCE_LINE: re.Pattern[str] = re.compile(r'^__version__: str = "(?P<version>[^"]*)"$', re.M)
NUMBER: str = r"(0|[1-9]\d*)"
TAG: re.Pattern[str] = re.compile(rf"^v{NUMBER}\.{NUMBER}\.{NUMBER}(?:-rc\.([1-9]\d*))?$")
FINAL: re.Pattern[str] = re.compile(rf"^{NUMBER}\.{NUMBER}\.{NUMBER}$")
PARTS: tuple[str, ...] = ("major", "minor", "patch")


class ReleaseError(Exception):
    pass


@dataclass(frozen=True)
class Release:
    major: int
    minor: int
    patch: int
    candidate: int | None = None

    @property
    def final(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @property
    def semver(self) -> str:
        return self.final if self.candidate is None else f"{self.final}-rc.{self.candidate}"

    @property
    def pep440(self) -> str:
        return self.final if self.candidate is None else f"{self.final}rc{self.candidate}"

    @property
    def tag(self) -> str:
        return f"v{self.semver}"

    @property
    def line(self) -> str:
        return f"{self.major}.{self.minor}"

    @property
    def is_candidate(self) -> bool:
        return self.candidate is not None

    @property
    def key(self) -> tuple[int, int, int, int]:
        return (self.major, self.minor, self.patch, self.candidate or sys.maxsize)

    def as_final(self) -> Release:
        return Release(self.major, self.minor, self.patch)

    def bumped(self, part: str) -> Release:
        if part == "major":
            return Release(self.major + 1, 0, 0)
        if part == "minor":
            return Release(self.major, self.minor + 1, 0)
        return Release(self.major, self.minor, self.patch + 1)


def parse_tag(tag: str) -> Release:
    match: re.Match[str] | None = TAG.match(tag)
    if match is None:
        raise ReleaseError(f"{tag!r} is not a release tag: vX.Y.Z or vX.Y.Z-rc.N")
    candidate: str | None = match.group(4)
    return Release(
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3)),
        None if candidate is None else int(candidate),
    )


def parse_final(version: str) -> Release:
    match: re.Match[str] | None = FINAL.match(version)
    if match is None:
        raise ReleaseError(f"{version!r} is not a final version: X.Y.Z")
    return Release(int(match.group(1)), int(match.group(2)), int(match.group(3)))


def read_source(source: Path = SOURCE) -> str:
    match: re.Match[str] | None = SOURCE_LINE.search(source.read_text(encoding="utf-8"))
    if match is None:
        raise ReleaseError(f'{source} has no `__version__: str = "…"` line')
    return match.group("version")


def write_source(version: str, source: Path = SOURCE) -> None:
    text: str = source.read_text(encoding="utf-8")
    source.write_text(
        SOURCE_LINE.sub(f'__version__: str = "{version}"', text, count=1), encoding="utf-8"
    )


def current(source: Path = SOURCE) -> Release:
    return parse_final(read_source(source))


def check(tag: str | None, source: Path = SOURCE, notes: Path = CHANGELOG) -> Release:
    version: Release = current(source)
    if tag is None:
        return version
    tagged: Release = parse_tag(tag)
    if tagged.final != version.final:
        raise ReleaseError(f"the tag is {tag} but the source says {version.final}")
    if changelog.section(notes.read_text(encoding="utf-8"), version.final) is None:
        raise ReleaseError(f"{notes.name} has no `## [{version.final}]` section")
    return tagged


def stamp(tag: str | None, dev: int | None, source: Path = SOURCE) -> str:
    version: Release = current(source)
    if tag is not None:
        tagged: Release = parse_tag(tag)
        if tagged.final != version.final:
            raise ReleaseError(f"the tag is {tag} but the source says {version.final}")
        stamped: str = tagged.pep440
    elif dev is not None and dev >= 0:
        stamped = f"{version.final}.dev{dev}"
    else:
        raise ReleaseError("stamp needs a tag or a non-negative build number")
    write_source(stamped, source)
    return stamped


def set_version(version: str, source: Path = SOURCE) -> Release:
    wanted: Release = parse_final(version)
    if wanted.key < current(source).key:
        raise ReleaseError(f"{version} is below {current(source).final}")
    write_source(wanted.final, source)
    return wanted


def prepare(day: date, source: Path = SOURCE, notes: Path = CHANGELOG) -> Release:
    version: Release = current(source)
    notes.write_text(
        changelog.prepare(notes.read_text(encoding="utf-8"), version.final, day),
        encoding="utf-8",
    )
    return version


def describe(release: Release) -> dict[str, str]:
    return {
        "version": release.final,
        "semver": release.semver,
        "pep440": release.pep440,
        "tag": release.tag,
        "line": release.line,
    }


def parser() -> argparse.ArgumentParser:
    built: argparse.ArgumentParser = argparse.ArgumentParser(prog="python -m tools.release.version")
    commands: argparse._SubParsersAction[argparse.ArgumentParser] = built.add_subparsers(
        dest="command", required=True
    )
    commands.add_parser("show", help="the version in every form")
    checking: argparse.ArgumentParser = commands.add_parser(
        "check", help="the source holds X.Y.Z, and a tag matches it"
    )
    checking.add_argument("--tag")
    converting: argparse.ArgumentParser = commands.add_parser(
        "pep440", help="the package version a tag builds"
    )
    converting.add_argument("--tag", required=True)
    stamping: argparse.ArgumentParser = commands.add_parser(
        "stamp", help="CI only: write a candidate or nightly version before building"
    )
    target: argparse._MutuallyExclusiveGroup = stamping.add_mutually_exclusive_group(required=True)
    target.add_argument("--tag")
    target.add_argument("--dev", type=int)
    setting: argparse.ArgumentParser = commands.add_parser("set", help="move the source to X.Y.Z")
    setting.add_argument("version")
    bumping: argparse.ArgumentParser = commands.add_parser(
        "bump", help="move the source to the next version"
    )
    bumping.add_argument("part", choices=PARTS)
    commands.add_parser("prepare", help="date the unreleased changes as this version")
    noting: argparse.ArgumentParser = commands.add_parser(
        "notes", help="a version's changelog section"
    )
    noting.add_argument("version")
    return built


def main(argv: Sequence[str] | None = None) -> int:
    arguments: argparse.Namespace = parser().parse_args(argv)
    command: str = arguments.command
    try:
        if command == "show":
            print(json.dumps(describe(current()), indent=2))
        elif command == "check":
            print(check(arguments.tag).semver)
        elif command == "pep440":
            print(parse_tag(arguments.tag).pep440)
        elif command == "stamp":
            print(stamp(arguments.tag, arguments.dev))
        elif command == "set":
            print(set_version(arguments.version).final)
        elif command == "bump":
            print(set_version(current().bumped(arguments.part).final).final)
        elif command == "prepare":
            print(prepare(date.today()).final)
        else:
            found: changelog.Section | None = changelog.section(
                CHANGELOG.read_text(encoding="utf-8"), parse_final(arguments.version).final
            )
            if found is None:
                raise ReleaseError(f"{CHANGELOG.name} has no `## [{arguments.version}]` section")
            print(found.body)
    except (ReleaseError, changelog.ChangelogError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
