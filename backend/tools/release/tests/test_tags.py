from __future__ import annotations

import pytest

from tools.release import tags as tags_module
from tools.release.tags import Checked, Repository, check_tag, previous, releases
from tools.release.version import Release, ReleaseError, parse_tag

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


GOOD: dict[str, object] = {
    "isPrerelease": True,
    "isDraft": False,
    "author": {"login": "github-actions[bot]"},
    "assets": [{"name": "SHA256SUMS"}, {"name": "mesbah-0.1.0-rc.2-reference.tar.gz"}],
}


def repository(
    commits: dict[str, str],
    published: dict[str, dict[str, object]],
    branches: dict[str, set[str]] | None = None,
) -> Repository:
    on: dict[str, set[str]] = branches or {"main": set(commits.values())}
    return Repository(
        names=list(commits),
        commit_of=lambda tag: commits[tag],
        contains=lambda branch, commit: commit in on.get(branch, set()),
        released=published.get,
    )


@pytest.fixture(autouse=True)
def versions_agree(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tags_module, "check", lambda tag: parse_tag(tag))


def test_a_candidate_on_main_may_be_released() -> None:
    checked: Checked = check_tag("v0.1.0-rc.1", "abc", repository({"v0.1.0-rc.1": "abc"}, {}))

    assert checked.kind == "candidate"
    assert checked.outputs()["pep440"] == "0.1.0rc1"
    assert checked.outputs()["latest"] == "false"


def test_stable_needs_a_candidate_that_passed_on_the_same_commit() -> None:
    commits: dict[str, str] = {"v0.1.0-rc.1": "old", "v0.1.0-rc.2": "abc", "v0.1.0": "abc"}

    checked: Checked = check_tag("v0.1.0", "abc", repository(commits, {"v0.1.0-rc.2": GOOD}))

    assert checked.kind == "stable"
    assert checked.latest


@pytest.mark.parametrize(
    ("commits", "published", "message"),
    [
        ({"v0.1.0-rc.1": "old", "v0.1.0": "abc"}, {}, "no 0.1.0 candidate"),
        ({"v0.1.0-rc.2": "abc", "v0.1.0": "abc"}, {}, "never passed"),
        (
            {"v0.1.0-rc.2": "abc", "v0.1.0": "abc"},
            {"v0.1.0-rc.2": {**GOOD, "author": {"login": "someone"}}},
            "made by someone",
        ),
        (
            {"v0.1.0-rc.2": "abc", "v0.1.0": "abc"},
            {"v0.1.0-rc.2": {**GOOD, "assets": [{"name": "SHA256SUMS"}]}},
            "lacks mesbah-0.1.0-rc.2-reference.tar.gz",
        ),
        (
            {"v0.1.0-rc.2": "abc", "v0.1.0": "abc"},
            {"v0.1.0-rc.2": GOOD, "v0.1.0": GOOD},
            "released already",
        ),
    ],
)
def test_stable_is_refused_without_a_passed_candidate(
    commits: dict[str, str], published: dict[str, dict[str, object]], message: str
) -> None:
    with pytest.raises(ReleaseError, match=message):
        check_tag("v0.1.0", "abc", repository(commits, published))


def test_a_patch_comes_from_its_release_branch() -> None:
    commits: dict[str, str] = {"v0.1.0": "a", "v0.2.0": "b", "v0.1.1-rc.1": "c"}

    with pytest.raises(ReleaseError, match="release/0.1"):
        check_tag("v0.1.1-rc.1", "c", repository(commits, {}, {"main": {"a", "b", "c"}}))
    assert check_tag("v0.1.1-rc.1", "c", repository(commits, {}, {"release/0.1": {"c"}}))


def test_a_patch_to_an_older_line_is_not_the_latest() -> None:
    commits: dict[str, str] = {"v0.2.0": "b", "v0.1.1-rc.1": "c", "v0.1.1": "c"}
    view: dict[str, object] = {
        **GOOD,
        "assets": [{"name": "SHA256SUMS"}, {"name": "mesbah-0.1.1-rc.1-reference.tar.gz"}],
    }

    checked: Checked = check_tag(
        "v0.1.1", "c", repository(commits, {"v0.1.1-rc.1": view}, {"release/0.1": {"c"}})
    )

    assert not checked.latest
