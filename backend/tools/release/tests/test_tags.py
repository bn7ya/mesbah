from __future__ import annotations

from tools.release.tags import previous, releases
from tools.release.version import Release, parse_tag

TAGS: list[str] = [
    "v0.2.0-rc.1",
    "v0.1.0",
    "v0.1.1",
    "v0.1.0-rc.2",
    "nightly",
    "v0.2.0",
    "v1.0.0-rc.1",
]


def test_only_release_tags_count_and_they_sort_by_version() -> None:
    found: list[str] = [release.tag for release in releases(TAGS)]

    assert found == ["v0.1.0-rc.2", "v0.1.0", "v0.1.1", "v0.2.0-rc.1", "v0.2.0", "v1.0.0-rc.1"]


def test_the_previous_release_is_the_last_stable_one_before() -> None:
    def before(tag: str) -> str | None:
        found: Release | None = previous(parse_tag(tag), TAGS)
        return None if found is None else found.tag

    assert before("v0.2.0-rc.1") == "v0.1.1"
    assert before("v0.2.0") == "v0.1.1"
    assert before("v1.0.0-rc.1") == "v0.2.0"
    assert before("v0.1.0-rc.1") is None
