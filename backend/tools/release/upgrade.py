from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

from tools.release.tags import previous, tags
from tools.release.version import BACKEND, REPOSITORY, Release

WHEEL_VERSION: re.Pattern[str] = re.compile(r"^mesbah-(\d+)\.(\d+)\.(\d+)(\S*?)-py3-none-any\.whl$")


class UpgradeError(Exception):
    pass


@dataclass(frozen=True)
class Step:
    name: str
    ok: bool
    seconds: float
    detail: str = ""


@dataclass
class Report:
    new: str
    previous: str | None = None
    skipped: bool = False
    reason: str = ""
    steps: list[Step] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.skipped or (bool(self.steps) and all(step.ok for step in self.steps))

    def write(self, path: Path) -> None:
        path.write_text(
            json.dumps({**asdict(self), "ok": self.ok}, indent=2) + "\n", encoding="utf-8"
        )


def release_of(wheel: Path) -> tuple[Release, str]:
    match: re.Match[str] | None = WHEEL_VERSION.match(wheel.name)
    if match is None:
        raise UpgradeError(f"{wheel.name} is not a Mesbah wheel")
    found: Release = Release(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return found, f"{found.final}{match.group(4)}"


def run(command: list[str], cwd: Path = BACKEND, environment: dict[str, str] | None = None) -> str:
    try:
        return subprocess.run(  # noqa: S603 - commands this tool builds
            command, cwd=cwd, env=environment, capture_output=True, check=True, text=True
        ).stdout
    except subprocess.CalledProcessError as error:
        printed: str = (error.stdout or "") + (error.stderr or "")
        raise UpgradeError(
            f"{' '.join(command[:4])} … exited {error.returncode}\n{printed[-3000:]}"
        ) from error


def checksum_matches(wheel: Path, sums: Path) -> bool:
    digest: str = hashlib.sha256(wheel.read_bytes()).hexdigest()
    return any(
        line.split()[:1] == [digest] and line.rstrip().endswith(wheel.name)
        for line in sums.read_text(encoding="utf-8").splitlines()
    )


def fetch(release: Release, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    try:
        run(
            ["gh", "release", "download", release.tag, "-p", "mesbah-*.whl", "-p", "SHA256SUMS"]
            + ["-D", str(folder), "--clobber"],
            cwd=REPOSITORY,
        )
        wheel: Path = next(folder.glob("mesbah-*.whl"))
        if not checksum_matches(wheel, folder / "SHA256SUMS"):
            raise UpgradeError(f"{wheel.name} does not match the release's SHA256SUMS")
        return wheel
    except (UpgradeError, FileNotFoundError, StopIteration):
        run(
            [sys.executable, "-m", "pip", "download", f"mesbah=={release.pep440}", "--no-deps"]
            + ["-d", str(folder)]
        )
        return next(folder.glob("mesbah-*.whl"))


@dataclass
class Upgrade:
    arguments: argparse.Namespace
    report: Report

    @property
    def work(self) -> Path:
        path: Path = self.arguments.work
        return path.resolve()

    @property
    def mesbah(self) -> Path:
        return self.work / "venv" / "bin" / "mesbah"

    @property
    def pip(self) -> list[str]:
        command: list[str] = [
            str(self.work / "venv" / "bin" / "python"),
            "-m",
            "pip",
            "install",
            "-q",
        ]
        if self.arguments.find_links:
            command += ["--find-links", str(self.arguments.find_links)]
        return command

    def environment(self) -> dict[str, str]:
        database: str | None = self.arguments.database_url
        return {**os.environ, **({"DATABASE_URL": database} if database else {})}

    def step(self, name: str, *command: str, cwd: Path = BACKEND) -> str:
        started: float = time.monotonic()
        try:
            printed: str = run(list(command), cwd, self.environment())
        except UpgradeError as error:
            self.report.steps.append(Step(name, False, time.monotonic() - started, str(error)))
            raise
        self.report.steps.append(
            Step(name, True, time.monotonic() - started, printed.strip()[-500:])
        )
        return printed

    def stack(self, name: str, out: str, *extra: str) -> None:
        database: list[str] = (
            ["--database-url", self.arguments.database_url] if self.arguments.database_url else []
        )
        self.step(
            name,
            sys.executable,
            "-m",
            "tools.release.stack",
            "start",
            "--mesbah",
            str(self.mesbah),
            "--engine-python",
            self.arguments.engine_python,
            "--data",
            str(self.work / "data"),
            "--out",
            str(self.work / out),
            *database,
            *extra,
        )

    def stop(self, name: str, out: str) -> None:
        self.step(
            name, sys.executable, "-m", "tools.release.stack", "stop", "--out", str(self.work / out)
        )

    def run(self, old: Path, seed_ref: str) -> None:
        new: Path = self.arguments.new.resolve()
        self.step("make a venv", self.arguments.python, "-m", "venv", str(self.work / "venv"))
        self.step("install the previous release", *self.pip, str(old))
        seeds: Path = BACKEND
        if seed_ref != ".":
            tools: Path = self.work / "seed"
            tools.mkdir(parents=True, exist_ok=True)
            self.step(
                "take the previous release's seed script",
                "sh",
                "-c",
                f"git archive {seed_ref} backend/tools | tar -x -C {tools}",
                cwd=REPOSITORY,
            )
            seeds = tools / "backend"
        self.stack("start the previous release", "old")
        try:
            self.step(
                "seed it through its own API",
                sys.executable,
                "-m",
                "tools.release.seed",
                "--stack",
                str(self.work / "old"),
                "--state",
                str(self.work / "state.json"),
                cwd=seeds,
            )
        finally:
            self.stop("stop the previous release", "old")
        self.step("upgrade the install in place", *self.pip, str(new))
        version: str = self.step(
            "the upgraded command names its version", str(self.mesbah), "--version"
        )
        if self.report.new not in version:
            raise UpgradeError(
                f"the upgraded install says {version.strip()}, not {self.report.new}"
            )
        plan: str = self.step(
            "plan the migrations",
            str(self.mesbah),
            "--data-dir",
            str(self.work / "data"),
            "manage",
            "migrate",
            "--plan",
        )
        (self.work / "migrate-plan.txt").write_text(plan, encoding="utf-8")
        self.stack("start the new release on the same data", "new", "--existing")
        try:
            self.step(
                "check everything the previous release made",
                sys.executable,
                "-m",
                "tools.release.verify",
                "--stack",
                str(self.work / "new"),
                "--state",
                str(self.work / "state.json"),
                "--mesbah",
                str(self.mesbah),
                "--report",
                str(self.work / "verify.json"),
            )
        finally:
            self.stop("stop the new release", "new")


def parser() -> argparse.ArgumentParser:
    built: argparse.ArgumentParser = argparse.ArgumentParser(prog="python -m tools.release.upgrade")
    built.add_argument("--new", type=Path, required=True, help="the wheel under test")
    built.add_argument("--work", type=Path, required=True, help="an empty folder to work in")
    built.add_argument(
        "--from", dest="old", type=Path, help="this wheel instead of the last release"
    )
    built.add_argument(
        "--seed-ref",
        help="the git ref whose seed script seeds it (default: its tag; `.`: this tree)",
    )
    built.add_argument("--find-links", type=Path, help="install from this folder too, offline")
    built.add_argument("--database-url", help="instead of the embedded PostgreSQL")
    built.add_argument("--python", default=sys.executable, help="the Python the install runs on")
    built.add_argument("--engine-python", default=sys.executable, help="runs the fake engine")
    return built


def main(argv: Sequence[str] | None = None) -> int:
    arguments: argparse.Namespace = parser().parse_args(argv)
    arguments.work.mkdir(parents=True, exist_ok=True)
    target: Release
    named: str
    target, named = release_of(arguments.new)
    report: Report = Report(new=named)
    upgrade: Upgrade = Upgrade(arguments, report)
    try:
        if arguments.old is not None:
            old: Path = arguments.old.resolve()
            report.previous = release_of(old)[1]
            seed_ref: str = arguments.seed_ref or "HEAD"
        else:
            earlier: Release | None = previous(target, tags())
            if earlier is None:
                report.skipped = True
                report.reason = f"no release before {target.final} to upgrade from"
                report.write(upgrade.work / "upgrade.json")
                print(f"Skipped: {report.reason}.")
                return 0
            report.previous = earlier.final
            old = fetch(earlier, upgrade.work / "previous")
            seed_ref = arguments.seed_ref or earlier.tag
        upgrade.run(old, seed_ref)
    except UpgradeError as error:
        print(f"error: {error}", file=sys.stderr)
    report.write(upgrade.work / "upgrade.json")
    for step in report.steps:
        print(f"{'ok' if step.ok else 'FAILED':6} {step.name} ({step.seconds:.0f} s)")
    print(f"{report.previous} → {report.new}: {'passed' if report.ok else 'FAILED'}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
