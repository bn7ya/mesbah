from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

UNRELEASED: str = "Unreleased"
HEADING: re.Pattern[str] = re.compile(
    r"^## \[(?P<name>[^\]]+)\](?: - (?P<day>\d{4}-\d{2}-\d{2}))?[ \t]*$", re.M
)


class ChangelogError(Exception):
    pass


@dataclass(frozen=True)
class Section:
    name: str
    day: str | None
    body: str
    start: int


def sections(text: str) -> list[Section]:
    headings: list[re.Match[str]] = list(HEADING.finditer(text))
    found: list[Section] = []
    for index, heading in enumerate(headings):
        end: int = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        body: str = text[heading.end() : end].strip()
        found.append(Section(heading["name"], heading["day"], body, heading.start()))
    return found


def section(text: str, name: str) -> Section | None:
    return next((found for found in sections(text) if found.name == name), None)


def prepare(text: str, version: str, day: date) -> str:
    if section(text, version) is not None:
        raise ChangelogError(f"the changelog already has a `## [{version}]` section")
    unreleased: Section | None = section(text, UNRELEASED)
    if unreleased is None or not unreleased.body:
        raise ChangelogError(f"the changelog has nothing under `## [{UNRELEASED}]` to release")
    rest: str = text[unreleased.start :].split("\n", 1)[1]
    return (
        f"{text[: unreleased.start]}## [{UNRELEASED}]\n\n## [{version}] - {day.isoformat()}\n{rest}"
    )
