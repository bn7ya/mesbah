from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pytest

from tools.release.stack import NOWHERE, Stack, alive, mesbah_command, offline, parser, stop


def arguments(*argv: str) -> argparse.Namespace:
    return parser().parse_args(["start", "--data", "/srv/data", "--out", "/srv/out", *argv])


def test_a_checkout_runs_with_the_python_that_runs_this() -> None:
    command: list[str] = mesbah_command(arguments())

    assert command[:3] == [sys.executable, "-m", "mesbah"]
    assert command[3:] == [
        "--data-dir",
        "/srv/data",
        "start",
        "--no-browser",
        "--port",
        "8177",
        "--engine-port",
        "8178",
    ]


def test_an_install_runs_its_own_command_and_can_use_another_database() -> None:
    command: list[str] = mesbah_command(
        arguments("--mesbah", "/venv/bin/mesbah", "--database-url", "postgresql://x/y")
    )

    assert command[0] == "/venv/bin/mesbah"
    assert command[-2:] == ["--database-url", "postgresql://x/y"]


def test_offline_points_every_proxy_nowhere_but_this_machine() -> None:
    environment: dict[str, str] = offline({"PATH": "/bin"})

    assert environment["HF_HUB_OFFLINE"] == "1"
    assert environment["HTTPS_PROXY"] == environment["http_proxy"] == NOWHERE
    assert "127.0.0.1" in environment["NO_PROXY"]
    assert environment["PATH"] == "/bin"


def test_a_stack_reads_back_what_it_wrote(tmp_path: Path) -> None:
    written: Stack = Stack("http://a", "http://b", "/d", "ABCD-EFGH", "0.1.0", 1, 2, "/l")

    written.write(tmp_path)

    assert Stack.read(tmp_path) == written


def test_stopping_reports_a_database_left_running(tmp_path: Path) -> None:
    data: Path = tmp_path / "data"
    (data / "postgres").mkdir(parents=True)
    (data / "postgres" / "postmaster.pid").write_text("1")
    Stack("http://a", "http://b", str(data), "code", "0.1.0", 2**22 + 7, 2**22 + 9, "/l").write(
        tmp_path
    )

    assert stop(tmp_path) == ["the embedded PostgreSQL is still running"]


def test_a_finished_process_is_not_alive() -> None:
    process: subprocess.Popen[bytes] = subprocess.Popen(["true"])  # noqa: S607
    process.wait()

    assert not alive(process.pid)


@pytest.mark.parametrize("command", [["stop"], ["start", "--data", "/d"]])
def test_each_command_needs_its_folders(command: list[str]) -> None:
    with pytest.raises(SystemExit):
        parser().parse_args(command)
