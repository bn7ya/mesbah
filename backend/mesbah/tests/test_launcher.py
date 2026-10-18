from __future__ import annotations

from pathlib import Path

import pytest

from mesbah import server
from mesbah.launcher import Launcher, Options, secret_key

DATABASE_URL: str = "postgresql://app:app@localhost:5432/app"


def launcher(data: Path, host: str = "127.0.0.1") -> Launcher:
    return Launcher(
        Options(host=host, port=8077, data_dir=data, database_url=DATABASE_URL, open_browser=False)
    )


def test_the_children_get_everything_they_need(tmp_path: Path) -> None:
    environment: dict[str, str] = launcher(tmp_path / "data").prepare()

    assert environment["DJANGO_SETTINGS_MODULE"] == "config.settings.local"
    assert environment["DATABASE_URL"] == DATABASE_URL
    assert environment["MESBAH_DATA_DIR"] == str(tmp_path / "data")
    assert str(server.server_root()) in environment["PYTHONPATH"]
    assert "http://127.0.0.1:8077" in environment["MESBAH_ORIGINS"].split(",")


def test_listening_everywhere_still_opens_on_this_machine(tmp_path: Path) -> None:
    assert launcher(tmp_path, host="0.0.0.0").address == "http://127.0.0.1:8077"  # noqa: S104


def test_the_secret_key_is_made_once_and_kept_private(tmp_path: Path) -> None:
    first: str = secret_key(tmp_path)

    assert secret_key(tmp_path) == first
    assert len(first) > 40
    assert (tmp_path / "secret-key").stat().st_mode & 0o777 == 0o600


def test_without_a_build_there_is_no_app_to_serve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(server, "PACKAGE_DIR", tmp_path)

    assert server.spa_dir() is None
    assert server.server_root() == tmp_path.parent


def test_a_built_app_is_found_beside_the_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "_spa").mkdir()
    (tmp_path / "_spa" / "index.html").write_text("<app-root></app-root>")
    (tmp_path / "_server").mkdir()
    monkeypatch.setattr(server, "PACKAGE_DIR", tmp_path)

    assert server.spa_dir() == tmp_path / "_spa"
    assert server.server_root() == tmp_path / "_server"
