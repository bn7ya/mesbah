from __future__ import annotations

from typing import Literal

type Role = Literal["viewers", "reviewers", "trainers", "admins"]

VIEWERS: Role = "viewers"
REVIEWERS: Role = "reviewers"
TRAINERS: Role = "trainers"
ADMINS: Role = "admins"

LADDER: tuple[Role, ...] = (VIEWERS, REVIEWERS, TRAINERS, ADMINS)


def rank(role: Role) -> int:
    return LADDER.index(role)


def highest(groups: list[str], *, superuser: bool = False) -> Role | None:
    if superuser:
        return ADMINS
    held: list[Role] = [role for role in LADDER if role in groups]
    return held[-1] if held else None


def at_least(role: Role) -> tuple[Role, ...]:
    return LADDER[rank(role) :]
