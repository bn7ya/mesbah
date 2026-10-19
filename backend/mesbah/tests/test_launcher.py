from __future__ import annotations

import signal
from pathlib import Path

import pytest

from mesbah import server
from mesbah.launcher import Launcher, Options, StepFailed, secret_key, tail

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


def test_the_web_side_gets_the_engine_address_and_a_fresh_token(tmp_path: Path) -> None:
    first: dict[str, str] = launcher(tmp_path).prepare()
    second: dict[str, str] = launcher(tmp_path).prepare()

    assert first["MESBAH_RUNTIME_URL"] == "http://127.0.0.1:8078"
    assert len(first["MESBAH_RUNTIME_TOKEN"]) > 30
    assert first["MESBAH_RUNTIME_TOKEN"] != second["MESBAH_RUNTIME_TOKEN"]


class Recorder:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str], **options: object) -> Recorder:
        self.commands.append(command)
        return self


@pytest.mark.parametrize("installed", [True, False])
def test_the_engine_starts_only_with_the_training_parts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, installed: bool
) -> None:
    recorder: Recorder = Recorder()
    monkeypatch.setattr("subprocess.Popen", recorder)
    monkeypatch.setattr("mesbah.launcher.engine_installed", lambda: installed)

    launcher(tmp_path).start({})

    modules: list[str] = [command[2] for command in recorder.commands]
    assert ("mesbah.runtime" in modules) is installed
    assert {"uvicorn", "celery"} <= set(modules)


def test_a_failed_step_names_itself_and_keeps_what_it_printed(tmp_path: Path) -> None:
    starting: Launcher = launcher(tmp_path / "data")
    environment: dict[str, str] = starting.prepare()

    with pytest.raises(StepFailed) as failed:
        starting.manage(environment, "no_such_command")

    assert failed.value.step == "no_such_command"
    assert "Unknown command: 'no_such_command'" in failed.value.output


def test_starting_stops_at_a_failed_step_and_says_why(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    starting: Launcher = launcher(tmp_path / "data")

    def fail(environment: dict[str, str], *arguments: str) -> str:
        raise StepFailed(arguments[0], "django.db.utils.ProgrammingError: relation missing")

    monkeypatch.setattr(starting, "manage", fail)
    monkeypatch.setattr(signal, "signal", lambda signum, handler: None)

    assert starting.run() == 1
    printed: str = capsys.readouterr().err
    assert "Mesbah could not start: `migrate` failed." in printed
    assert "ProgrammingError: relation missing" in printed


def test_only_the_end_of_a_long_output_is_kept() -> None:
    printed: bytes = "\n".join(f"line {number}" for number in range(100)).encode()

    kept: list[str] = tail(printed, b"the error").splitlines()

    assert len(kept) == 40
    assert kept[-1] == "the error"
