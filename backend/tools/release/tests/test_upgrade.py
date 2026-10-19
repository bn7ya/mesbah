from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.release import upgrade
from tools.release.seed import events
from tools.release.upgrade import Report, Step, UpgradeError, checksum_matches, release_of


def test_a_wheel_names_its_release_and_version() -> None:
    assert release_of(Path("mesbah-0.2.0rc1-py3-none-any.whl"))[1] == "0.2.0rc1"
    assert release_of(Path("mesbah-1.4.2-py3-none-any.whl"))[0].final == "1.4.2"
    with pytest.raises(UpgradeError):
        release_of(Path("other-1.0.0-py3-none-any.whl"))


def test_a_downloaded_wheel_must_match_its_checksum(tmp_path: Path) -> None:
    wheel: Path = tmp_path / "mesbah-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"wheel")
    digest: str = hashlib.sha256(b"wheel").hexdigest()
    sums: Path = tmp_path / "SHA256SUMS"

    sums.write_text(f"{digest}  mesbah-0.1.0-py3-none-any.whl\n")
    assert checksum_matches(wheel, sums)
    sums.write_text(f"{'0' * 64}  mesbah-0.1.0-py3-none-any.whl\n")
    assert not checksum_matches(wheel, sums)


def test_a_report_passes_only_when_every_step_did() -> None:
    assert not Report(new="0.2.0").ok
    assert Report(new="0.2.0", skipped=True).ok
    assert Report(new="0.2.0", steps=[Step("a", True, 1.0)]).ok
    assert not Report(new="0.2.0", steps=[Step("a", True, 1.0), Step("b", False, 2.0)]).ok


def test_with_no_release_before_it_the_upgrade_is_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(upgrade, "tags", lambda: ["v0.1.0-rc.1"])

    code: int = upgrade.main(
        ["--new", "mesbah-0.1.0-py3-none-any.whl", "--work", str(tmp_path / "work")]
    )

    written: object = json.loads((tmp_path / "work" / "upgrade.json").read_text())
    assert code == 0
    assert isinstance(written, dict)
    assert written["skipped"] is True
    assert written["ok"] is True


def test_a_reply_stream_reads_as_its_events() -> None:
    stream: bytes = (
        b': keepalive\n\nevent: start\ndata: {"asked": {}}\n\n'
        b'event: content\ndata: {"text": "Hi"}\n\nevent: done\ndata: {"reply": {"id": "r1"}}\n\n'
    )

    assert [name for name, _ in events(stream)] == ["start", "content", "done"]
    assert events(stream)[-1][1] == {"reply": {"id": "r1"}}
