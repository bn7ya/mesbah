from __future__ import annotations

import json
from pathlib import Path

import pytest
from django.core.management import call_command

from contracts import Contract


@pytest.mark.contract
def test_the_api_schema_is_what_the_release_promises(contract: Contract, tmp_path: Path) -> None:
    written: Path = tmp_path / "schema.json"
    call_command("spectacular", "--format", "openapi-json", "--file", str(written))
    schema: dict[str, object] = json.loads(written.read_text(encoding="utf-8"))
    info: object = schema.get("info")
    assert isinstance(info, dict)
    info.pop("version")

    contract.check("openapi.json", schema)
