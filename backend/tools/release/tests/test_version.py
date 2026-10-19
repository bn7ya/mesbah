from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings

from mesbah import __version__

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
