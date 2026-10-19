from __future__ import annotations

import pytest

from tools.release.contracts import Verdict, allowed, compare, snapshots
from tools.release.version import parse_tag

PATHS: dict[str, object] = {"/api/projects/": {"get": {"description": "words"}, "post": {}}}
SCHEMAS: dict[str, object] = {
    "Project": {"properties": {"name": {"type": "string"}}, "required": ["name"]},
    "NewProjectRequest": {"properties": {"name": {"type": "string"}}, "required": ["name"]},
    "KindEnum": {"enum": ["finetune", "scratch"]},
}


def schema(paths: dict[str, object], schemas: dict[str, object]) -> dict[str, object]:
    return {"paths": paths, "components": {"schemas": schemas}}


SCHEMA: dict[str, object] = schema(PATHS, SCHEMAS)


def with_schema(change: dict[str, object]) -> dict[str, object]:
    return {"openapi.json": change, "migrations.json": {"chat": {"0001_initial": "aa"}}}


def kinds(verdict: Verdict) -> set[str]:
    return {change.kind for change in verdict.changes}


def test_nothing_changed_is_none() -> None:
    assert compare(with_schema(SCHEMA), with_schema(SCHEMA)).kind == "none"


def test_a_description_is_not_a_contract() -> None:
    edited: dict[str, object] = schema(
        {"/api/projects/": {"get": {"description": "other words"}, "post": {}}}, SCHEMAS
    )

    assert compare(with_schema(SCHEMA), with_schema(edited)).kind == "none"


def test_a_new_path_or_enum_value_is_additive_and_a_removed_one_breaking() -> None:
    wider: dict[str, object] = schema(
        {**PATHS, "/api/projects/{id}/": {"get": {}}},
        {**SCHEMAS, "KindEnum": {"enum": ["finetune", "scratch", "imported"]}},
    )

    assert compare(with_schema(SCHEMA), with_schema(wider)).kind == "additive"
    assert compare(with_schema(wider), with_schema(SCHEMA)).kind == "breaking"


def test_a_request_field_made_required_breaks_and_a_type_change_breaks() -> None:
    stricter: dict[str, object] = schema(
        PATHS,
        {
            **SCHEMAS,
            "NewProjectRequest": {
                "properties": {"name": {"type": "string"}, "notes": {"type": "string"}},
                "required": ["name", "notes"],
            },
            "Project": {"properties": {"name": {"type": "integer"}}, "required": ["name"]},
        },
    )

    verdict: Verdict = compare(with_schema(SCHEMA), with_schema(stricter))
    assert verdict.kind == "breaking"
    assert any("required" in change.what for change in verdict.changes if change.kind == "breaking")


def test_an_edited_or_missing_migration_blocks_and_a_new_one_is_additive() -> None:
    old: dict[str, object] = {"migrations.json": {"chat": {"0001_initial": "aa"}}}

    assert compare(old, {"migrations.json": {"chat": {"0001_initial": "bb"}}}).kind == "blocking"
    assert compare(old, {"migrations.json": {"chat": {}}}).kind == "blocking"
    grown: Verdict = compare(
        old, {"migrations.json": {"chat": {"0001_initial": "aa", "0002": "cc"}}}
    )
    assert grown.kind == "additive"
    assert grown.only_new_migrations()


def test_the_internal_files_change_without_promising_anything() -> None:
    verdict: Verdict = compare({"files.json": {"a": 1}}, {"files.json": {"a": 2}})

    assert kinds(verdict) == {"internal"}


@pytest.mark.parametrize(
    ("kind", "before", "after", "refused"),
    [
        ("breaking", "v0.1.0", "v0.2.0", False),
        ("breaking", "v1.1.0", "v1.2.0", True),
        ("breaking", "v1.1.0", "v2.0.0", False),
        ("additive", "v0.1.0", "v0.1.1", True),
        ("additive", "v0.1.0", "v0.2.0-rc.1", False),
        ("none", "v0.1.0", "v0.1.1", False),
    ],
)
def test_the_bump_must_be_as_large_as_the_change(
    kind: str, before: str, after: str, refused: bool
) -> None:
    changes: dict[str, tuple[dict[str, object], dict[str, object]]] = {
        "breaking": (with_schema(SCHEMA), with_schema(schema({}, SCHEMAS))),
        "additive": (with_schema(schema({}, SCHEMAS)), with_schema(SCHEMA)),
        "none": (with_schema(SCHEMA), with_schema(SCHEMA)),
    }
    verdict: Verdict = compare(*changes[kind])

    assert verdict.kind == kind
    assert (allowed(verdict, parse_tag(before), parse_tag(after)) is not None) is refused


def test_a_patch_may_add_a_migration() -> None:
    verdict: Verdict = compare(
        {"migrations.json": {"chat": {"0001": "aa"}}},
        {"migrations.json": {"chat": {"0001": "aa", "0002": "bb"}}},
    )

    assert allowed(verdict, parse_tag("v0.1.0"), parse_tag("v0.1.1")) is None


def test_the_tree_matches_itself() -> None:
    assert compare(snapshots(None), snapshots(None)).kind == "none"


def test_a_new_request_with_required_fields_breaks_nothing() -> None:
    added: dict[str, object] = schema(
        PATHS,
        {**SCHEMAS, "NewKeyRequest": {"properties": {"name": {}}, "required": ["name"]}},
    )

    assert compare(with_schema(SCHEMA), with_schema(added)).kind == "additive"
