from __future__ import annotations

from datetime import date

import pytest

from tools.release.changelog import ChangelogError, Section, prepare, section, sections

NOTES: str = """# Changelog

Intro.

## [Unreleased]

### Fixed

- Something new.

## [0.2.0] - 2026-11-01

### Added

- A feature.

## [0.1.0] - 2026-10-19

The first release.
"""


def test_every_version_heading_is_a_section() -> None:
    found: list[tuple[str, str | None]] = [(each.name, each.day) for each in sections(NOTES)]

    assert found == [("Unreleased", None), ("0.2.0", "2026-11-01"), ("0.1.0", "2026-10-19")]


def test_a_section_holds_everything_up_to_the_next_version() -> None:
    found: Section | None = section(NOTES, "0.2.0")

    assert found is not None
    assert found.body == "### Added\n\n- A feature."
    assert section(NOTES, "0.3.0") is None


def test_preparing_moves_the_unreleased_changes_under_the_version() -> None:
    prepared: str = prepare(NOTES, "0.2.1", date(2026, 11, 5))
    released: Section | None = section(prepared, "0.2.1")
    unreleased: Section | None = section(prepared, "Unreleased")

    assert released is not None and released.body == "### Fixed\n\n- Something new."
    assert released.day == "2026-11-05"
    assert unreleased is not None and unreleased.body == ""
    assert prepared.startswith("# Changelog\n\nIntro.\n\n## [Unreleased]\n\n## [0.2.1] - ")


def test_preparing_refuses_nothing_to_release_or_a_version_twice() -> None:
    with pytest.raises(ChangelogError, match="already"):
        prepare(NOTES, "0.2.0", date(2026, 11, 5))
    with pytest.raises(ChangelogError, match="nothing"):
        prepare(prepare(NOTES, "0.2.1", date(2026, 11, 5)), "0.2.2", date(2026, 11, 6))
