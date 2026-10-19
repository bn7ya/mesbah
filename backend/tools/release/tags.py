from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from tools.release.version import REPOSITORY, Release, ReleaseError, check, parse_tag


def tags() -> list[str]:
    listed: str = git("tag", "--list", "v*").stdout
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


BOT: str = "github-actions[bot]"


@dataclass(frozen=True)
class Checked:
    release: Release
    commit: str
    latest: bool

    @property
    def kind(self) -> str:
        return "candidate" if self.release.is_candidate else "stable"

    def outputs(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "tag": self.release.tag,
            "semver": self.release.semver,
            "pep440": self.release.pep440,
            "final": self.release.final,
            "commit": self.commit,
            "latest": "true" if self.latest else "false",
        }


@dataclass(frozen=True)
class Repository:
    names: list[str]
    commit_of: Callable[[str], str]
    contains: Callable[[str, str], bool]
    released: Callable[[str], dict[str, object] | None]


def git(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - git with arguments this tool builds
        ["git", *arguments],  # noqa: S607
        cwd=REPOSITORY,
        capture_output=True,
        check=False,
        text=True,
    )


def commit_of(ref: str) -> str:
    found: subprocess.CompletedProcess[str] = git("rev-list", "-n", "1", ref)
    if found.returncode != 0:
        raise ReleaseError(f"{ref} names no commit")
    return found.stdout.strip()


def contains(branch: str, commit: str) -> bool:
    return git("merge-base", "--is-ancestor", commit, f"origin/{branch}").returncode == 0


def released(tag: str) -> dict[str, object] | None:
    shown: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603 - gh with a tag
        ["gh", "release", "view", tag, "--json", "isPrerelease,isDraft,author,assets"],  # noqa: S607
        cwd=REPOSITORY,
        capture_output=True,
        check=False,
        text=True,
    )
    if shown.returncode != 0:
        return None
    found: object = json.loads(shown.stdout)
    return found if isinstance(found, dict) else None


def candidate_problem(view: dict[str, object] | None, candidate: Release) -> str | None:
    if view is None:
        return f"{candidate.tag} has no GitHub release, so its bundle never passed"
    author: object = view.get("author")
    login: object = author.get("login") if isinstance(author, dict) else None
    assets: object = view.get("assets")
    names: set[str] = (
        {str(asset.get("name")) for asset in assets if isinstance(asset, dict)}
        if isinstance(assets, list)
        else set()
    )
    wanted: set[str] = {"SHA256SUMS", f"mesbah-{candidate.semver}-reference.tar.gz"}
    if view.get("isPrerelease") is not True or view.get("isDraft") is not False:
        return f"{candidate.tag}'s GitHub release is not a published pre-release"
    if login != BOT:
        return f"{candidate.tag}'s GitHub release was made by {login}, not by the release workflow"
    if not wanted <= names:
        return f"{candidate.tag}'s GitHub release lacks {', '.join(sorted(wanted - names))}"
    return None


def check_tag(tag: str, commit: str, repository: Repository) -> Checked:
    release: Release = parse_tag(tag)
    check(tag)
    branch: str = "main" if release.patch == 0 else f"release/{release.line}"
    if not repository.contains(branch, commit):
        raise ReleaseError(f"{tag} is not on {branch}, where {release.final} is released from")
    if repository.released(tag) is not None:
        raise ReleaseError(f"{tag} is released already; a version is never released twice")
    if release.is_candidate:
        return Checked(release, commit, latest=False)
    candidates: list[Release] = [
        found
        for found in releases(repository.names)
        if found.is_candidate
        and found.final == release.final
        and repository.commit_of(found.tag) == commit
    ]
    if not candidates:
        raise ReleaseError(f"no {release.final} candidate was tagged on this commit")
    problem: str | None = candidate_problem(repository.released(candidates[-1].tag), candidates[-1])
    if problem is not None:
        raise ReleaseError(problem)
    stable: list[Release] = [
        found for found in releases(repository.names) if not found.is_candidate
    ]
    return Checked(release, commit, latest=all(found.key <= release.key for found in stable))


def main(argv: Sequence[str] | None = None) -> int:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(prog="python -m tools.release.tags")
    commands: argparse._SubParsersAction[argparse.ArgumentParser] = parser.add_subparsers(
        dest="command", required=True
    )
    before: argparse.ArgumentParser = commands.add_parser(
        "previous", help="the last stable release before a tag, or nothing"
    )
    before.add_argument("tag")
    checking: argparse.ArgumentParser = commands.add_parser(
        "check", help="whether a tag may be released, and what it is"
    )
    checking.add_argument("tag")
    checking.add_argument("--commit", help="the commit, when the tag is not made yet (a rehearsal)")
    checking.add_argument("--github-output", type=Path, help="append the outputs here")
    arguments: argparse.Namespace = parser.parse_args(argv)
    try:
        if arguments.command == "previous":
            found: Release | None = previous(parse_tag(arguments.tag), tags())
            print("" if found is None else found.tag)
            return 0
        commit: str = arguments.commit or commit_of(arguments.tag)
        checked: Checked = check_tag(
            arguments.tag, commit, Repository(tags(), commit_of, contains, released)
        )
    except ReleaseError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    outputs: dict[str, str] = checked.outputs()
    if arguments.github_output:
        with arguments.github_output.open("a", encoding="utf-8") as written:
            written.writelines(f"{key}={value}\n" for key, value in outputs.items())
    print(f"{checked.release.tag}: a {checked.kind} release of {commit[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
