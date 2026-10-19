from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from django.conf import settings

from mesbah import __version__
from tools.release.version import (
    Release,
    ReleaseError,
    check,
    current,
    main,
    parse_tag,
    prepare,
    read_source,
    set_version,
    stamp,
)

BACKEND: Path = Path(__file__).resolve().parents[3]
FRONTEND: Path = BACKEND.parent / "frontend"


def read_json(path: Path) -> dict[str, object]:
    parsed: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def test_the_api_schema_reads_the_package_version() -> None:
    assert settings.SPECTACULAR_SETTINGS["VERSION"] == __version__


def test_the_frontend_package_carries_no_version_of_its_own() -> None:
    package: dict[str, object] = read_json(FRONTEND / "package.json")
    lock: dict[str, object] = read_json(FRONTEND / "package-lock.json")
    packages: object = lock.get("packages")
    root: object = packages.get("") if isinstance(packages, dict) else None

    assert "version" not in package
    assert "version" not in lock
    assert isinstance(root, dict)
    assert "version" not in root


def project(tmp_path: Path, version: str = "0.1.0", notes: str = "") -> tuple[Path, Path]:
    source: Path = tmp_path / "__init__.py"
    source.write_text(f'from __future__ import annotations\n\n__version__: str = "{version}"\n')
    changelog_file: Path = tmp_path / "CHANGELOG.md"
    changelog_file.write_text(notes or "# Changelog\n\n## [Unreleased]\n\n- Something.\n")
    return source, changelog_file


@pytest.mark.parametrize(
    ("tag", "semver", "pep440", "candidate"),
    [
        ("v0.1.0", "0.1.0", "0.1.0", False),
        ("v0.1.0-rc.1", "0.1.0-rc.1", "0.1.0rc1", True),
        ("v1.12.3-rc.10", "1.12.3-rc.10", "1.12.3rc10", True),
    ],
)
def test_a_tag_maps_to_its_package_version(
    tag: str, semver: str, pep440: str, candidate: bool
) -> None:
    release: Release = parse_tag(tag)

    assert (release.tag, release.semver, release.pep440) == (tag, semver, pep440)
    assert release.is_candidate is candidate


@pytest.mark.parametrize(
    "tag",
    ["0.1.0", "v0.1", "v0.1.0-rc1", "v0.1.0-rc.0", "v0.1.0-beta.1", "v01.1.0", "v0.1.0+local"],
)
def test_anything_else_is_not_a_release_tag(tag: str) -> None:
    with pytest.raises(ReleaseError):
        parse_tag(tag)


def test_a_candidate_sorts_before_its_release_and_after_the_one_before() -> None:
    ordered: list[str] = ["v0.9.9", "v0.10.0-rc.1", "v0.10.0-rc.2", "v0.10.0", "v0.10.1-rc.1"]

    shuffled: list[str] = [ordered[3], ordered[0], ordered[4], ordered[2], ordered[1]]

    assert sorted(shuffled, key=lambda tag: parse_tag(tag).key) == ordered


def test_the_source_must_hold_a_final_version(tmp_path: Path) -> None:
    source, notes = project(tmp_path, "0.1.0rc1")

    with pytest.raises(ReleaseError):
        check(None, source, notes)


def test_a_tag_must_match_the_source_and_have_notes(tmp_path: Path) -> None:
    source, notes = project(tmp_path, notes="## [Unreleased]\n\n## [0.1.0] - 2026-10-19\n\n- A.\n")

    assert check("v0.1.0-rc.2", source, notes).pep440 == "0.1.0rc2"
    with pytest.raises(ReleaseError, match="source says 0.1.0"):
        check("v0.2.0", source, notes)
    notes.write_text("## [Unreleased]\n\n- A.\n")
    with pytest.raises(ReleaseError, match="no `## \\[0.1.0\\]` section"):
        check("v0.1.0", source, notes)


def test_stamping_writes_the_candidate_or_nightly_version(tmp_path: Path) -> None:
    source, _ = project(tmp_path)

    assert stamp("v0.1.0-rc.3", None, source) == "0.1.0rc3"
    assert read_source(source) == "0.1.0rc3"
    source, _ = project(tmp_path)
    assert stamp(None, 42, source) == "0.1.0.dev42"
    source, _ = project(tmp_path)
    with pytest.raises(ReleaseError):
        stamp("v0.2.0-rc.1", None, source)


def test_the_version_only_moves_forward(tmp_path: Path) -> None:
    source, _ = project(tmp_path, "0.2.0")

    assert set_version("0.2.0", source).final == "0.2.0"
    assert set_version(current(source).bumped("minor").final, source).final == "0.3.0"
    assert current(source).bumped("major").final == "1.0.0"
    assert current(source).bumped("patch").final == "0.3.1"
    with pytest.raises(ReleaseError, match="below"):
        set_version("0.1.9", source)
    with pytest.raises(ReleaseError):
        set_version("0.4.0-rc.1", source)


def test_preparing_dates_the_unreleased_changes(tmp_path: Path) -> None:
    source, notes = project(tmp_path)

    prepare(date(2026, 10, 19), source, notes)

    assert notes.read_text() == (
        "# Changelog\n\n## [Unreleased]\n\n## [0.1.0] - 2026-10-19\n\n- Something.\n"
    )


def test_the_command_reports_errors_without_a_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["pep440", "--tag", "v0.1.0-rc.1"]) == 0
    assert capsys.readouterr().out == "0.1.0rc1\n"
    assert main(["pep440", "--tag", "v0.1"]) == 1
    assert "not a release tag" in capsys.readouterr().err
