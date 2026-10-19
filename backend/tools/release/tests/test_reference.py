from __future__ import annotations

import json
import tarfile
from pathlib import Path
from typing import IO

from tools.release.reference import main


def test_the_reference_holds_every_part_a_manifest_and_a_gallery(tmp_path: Path) -> None:
    dist: Path = tmp_path / "dist"
    dist.mkdir()
    (dist / "mesbah-0.1.0-py3-none-any.whl").write_bytes(b"PK wheel")
    screens: Path = tmp_path / "e2e" / "screens" / "ltr" / "chat"
    screens.mkdir(parents=True)
    (screens / "01-reply.png").write_bytes(b"\x89PNG")
    out: Path = tmp_path / "mesbah-0.1.0-reference.tar.gz"

    code: int = main(
        ["--version", "0.1.0", "--out", str(out), "--part", f"dist={dist}"]
        + ["--part", f"e2e={tmp_path / 'e2e'}", "--result", "e2e=success", "--note", "sha=abc"]
    )

    with tarfile.open(out) as archive:
        names: list[str] = archive.getnames()
        written: IO[bytes] | None = archive.extractfile("mesbah-0.1.0-reference/manifest.json")
        assert written is not None
        manifest: object = json.load(written)
    assert code == 0
    assert "mesbah-0.1.0-reference/dist/mesbah-0.1.0-py3-none-any.whl" in names
    assert "mesbah-0.1.0-reference/e2e/screens/index.html" in names
    assert isinstance(manifest, dict)
    assert manifest["sha"] == "abc"
    assert manifest["results"] == {"e2e": "success"}


def test_a_part_that_failed_fails_the_reference(tmp_path: Path) -> None:
    out: Path = tmp_path / "ref.tar.gz"

    assert main(["--version", "0.1.0", "--out", str(out), "--result", "upgrade=failure"]) == 1
    assert out.is_file()
