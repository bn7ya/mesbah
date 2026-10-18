from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING, Any

import httpx2
import pytest

from mesbah import parts
from mesbah.runtime.app import create_app
from mesbah.runtime.engine import Engine

if TYPE_CHECKING:
    from starlette.testclient import TestClient

TOKEN: str = "test-token"
INSTALLED: dict[str, str] = {"torch": "2.9.0+cu128", "peft": "0.17.1"}


def client() -> TestClient:
    # Starlette's TestClient imports httpx; Mesbah ships its successor under another name.
    if importlib.util.find_spec("httpx") is None:
        httpx2.alias_httpx()
    from starlette.testclient import TestClient

    return TestClient(create_app(Engine(), TOKEN), headers={"Authorization": f"Bearer {TOKEN}"})


def test_the_status_reports_the_parts_the_engine_sees(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(parts, "installed", INSTALLED.get)

    status: dict[str, Any] = client().get("/admin/status").json()

    assert status["loaded"] is False
    by_name: dict[str, str | None] = {row["name"]: row["version"] for row in status["parts"]}
    assert set(by_name) == {part_name for part_name, _ in parts.PARTS}
    assert by_name["torch"] == "2.9.0+cu128"
    assert by_name["peft"] == "0.17.1"
    assert by_name["trl"] is None
    assert all(set(row) == {"name", "version"} for row in status["parts"])
