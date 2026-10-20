from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

BACKEND: Path = Path(__file__).resolve().parents[2]
PORT: int = 8177
ENGINE_PORT: int = 8178
START_SECONDS: float = 180.0
STOP_SECONDS: float = 60.0
POLL_SECONDS: float = 0.5
NOWHERE: str = "http://127.0.0.1:9"
VERSION_LINE: re.Pattern[str] = re.compile(r"mesbah (\S+)")


class StackError(Exception):
    pass


@dataclass(frozen=True)
class Stack:
    base_url: str
    engine_url: str
    data_dir: str
    setup_code: str
    version: str
    mesbah_pid: int
    engine_pid: int
    logs: str

    @classmethod
    def read(cls, out: Path) -> Stack:
        found: object = json.loads((out / "stack.json").read_text(encoding="utf-8"))
        if not isinstance(found, dict):
            raise StackError(f"{out / 'stack.json'} is not a stack")
        return cls(**found)

    def write(self, out: Path) -> None:
        (out / "stack.json").write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")


def answers(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:  # noqa: S310 - a local address
            return int(response.status) == 200
    except (urllib.error.URLError, OSError):
        return False


def read_json(url: str) -> dict[str, object]:
    with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310 - a local address
        found: object = json.loads(response.read())
    return found if isinstance(found, dict) else {}


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    status: Path = Path(f"/proc/{pid}/status")
    return not status.exists() or "State:\tZ" not in status.read_text()


def wait_for(check: str, seconds: float, process: subprocess.Popen[bytes], log: Path) -> None:
    deadline: float = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if answers(check):
            return
        if process.poll() is not None:
            raise StackError(f"it exited with {process.returncode}; see {log}")
        time.sleep(POLL_SECONDS)
    raise StackError(f"{check} did not answer in {seconds:.0f} seconds; see {log}")


def launch(command: list[str], log: Path, environment: dict[str, str]) -> subprocess.Popen[bytes]:
    with log.open("ab") as written:
        return subprocess.Popen(  # noqa: S603 - commands this tool builds
            command,
            env=environment,
            cwd=BACKEND,
            stdout=written,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )


def offline(environment: dict[str, str]) -> dict[str, str]:
    return {
        **environment,
        "HF_HUB_OFFLINE": "1",
        "HTTPS_PROXY": NOWHERE,
        "HTTP_PROXY": NOWHERE,
        "https_proxy": NOWHERE,
        "http_proxy": NOWHERE,
        "NO_PROXY": "127.0.0.1,localhost",
        "no_proxy": "127.0.0.1,localhost",
    }


def mesbah_command(arguments: argparse.Namespace) -> list[str]:
    head: list[str] = (
        [arguments.python, "-m", "mesbah"] if arguments.mesbah == "checkout" else [arguments.mesbah]
    )
    command: list[str] = [
        *head,
        "--data-dir",
        str(arguments.data),
        "start",
        "--no-browser",
        "--port",
        str(arguments.port),
        "--engine-port",
        str(arguments.engine_port),
    ]
    if arguments.database_url:
        command += ["--database-url", arguments.database_url]
    return command


def version_of(command: list[str], environment: dict[str, str]) -> str:
    head: list[str] = command[: command.index("--data-dir")]
    printed: str = subprocess.run(  # noqa: S603 - the command this tool built
        [*head, "--version"], env=environment, cwd=BACKEND, capture_output=True, check=True
    ).stdout.decode()
    match: re.Match[str] | None = VERSION_LINE.search(printed)
    return match.group(1) if match else printed.strip()


def start(arguments: argparse.Namespace) -> Stack:
    data: Path = arguments.data.resolve()
    out: Path = arguments.out.resolve()
    used: bool = data.exists() and any(data.iterdir())
    if used and not arguments.existing:
        raise StackError(f"{data} is not empty; the journeys start from a fresh data folder")
    if arguments.existing and not used:
        raise StackError(f"{data} holds no install to start again")
    if answers(f"http://127.0.0.1:{arguments.port}/api/health/"):
        raise StackError(f"something already answers on port {arguments.port}")
    data.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    environment: dict[str, str] = {
        **os.environ,
        "MESBAH_FAKE_TRAINER": "1",
        "PYTHONPATH": str(BACKEND) if arguments.mesbah == "checkout" else "",
    }
    if not arguments.online:
        environment = offline(environment)
    engine_log: Path = out / "engine.log"
    engine: subprocess.Popen[bytes] = launch(
        [
            arguments.engine_python,
            "-m",
            "mesbah.runtime",
            "--fake",
            "--port",
            str(arguments.engine_port),
        ],
        engine_log,
        {**environment, "PYTHONPATH": str(BACKEND)},
    )
    engine_url: str = f"http://127.0.0.1:{arguments.engine_port}"
    wait_for(f"{engine_url}/health", 30, engine, engine_log)
    command: list[str] = mesbah_command(arguments)
    mesbah_log: Path = out / "mesbah.log"
    mesbah: subprocess.Popen[bytes] = launch(command, mesbah_log, environment)
    base_url: str = f"http://127.0.0.1:{arguments.port}"
    try:
        wait_for(f"{base_url}/api/health/", START_SECONDS, mesbah, mesbah_log)
        fresh: bool = not arguments.existing
        if read_json(f"{base_url}/api/auth/setup/").get("needed") is not fresh:
            raise StackError(
                "an install that has its owner asks for setup again"
                if arguments.existing
                else "a fresh Mesbah should ask for its first-run setup"
            )
    except StackError:
        stop_process(mesbah.pid, STOP_SECONDS)
        stop_process(engine.pid, 10)
        raise
    stack: Stack = Stack(
        base_url=base_url,
        engine_url=engine_url,
        data_dir=str(data),
        setup_code=setup_code(data),
        version=version_of(command, environment),
        mesbah_pid=mesbah.pid,
        engine_pid=engine.pid,
        logs=str(out),
    )
    stack.write(out)
    return stack


def setup_code(data: Path) -> str:
    written: Path = data / "setup-code"
    return written.read_text(encoding="utf-8").strip() if written.is_file() else ""


def stop_process(pid: int, seconds: float) -> bool:
    if not alive(pid):
        return True
    os.kill(pid, signal.SIGTERM)
    deadline: float = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not alive(pid):
            return True
        time.sleep(POLL_SECONDS)
    os.kill(pid, signal.SIGKILL)
    return False


def stop(out: Path) -> list[str]:
    stack: Stack = Stack.read(out)
    problems: list[str] = []
    if not stop_process(stack.mesbah_pid, STOP_SECONDS):
        problems.append(f"Mesbah did not stop within {STOP_SECONDS:.0f} seconds")
    if (Path(stack.data_dir) / "postgres" / "postmaster.pid").exists():
        problems.append("the embedded PostgreSQL is still running")
    if not stop_process(stack.engine_pid, 10):
        problems.append("the fake engine did not stop")
    return problems


def parser() -> argparse.ArgumentParser:
    built: argparse.ArgumentParser = argparse.ArgumentParser(prog="python -m tools.release.stack")
    commands: argparse._SubParsersAction[argparse.ArgumentParser] = built.add_subparsers(
        dest="command", required=True
    )
    starting: argparse.ArgumentParser = commands.add_parser(
        "start", help="start Mesbah and the fake engine for the journeys, then return"
    )
    starting.add_argument(
        "--mesbah", default="checkout", help="the `mesbah` command of an install, or `checkout`"
    )
    starting.add_argument("--python", default=sys.executable, help="runs a checkout")
    starting.add_argument(
        "--engine-python", default=sys.executable, help="a Python with starlette and uvicorn"
    )
    starting.add_argument("--data", type=Path, required=True)
    starting.add_argument("--out", type=Path, required=True)
    starting.add_argument("--port", type=int, default=PORT)
    starting.add_argument("--engine-port", type=int, default=ENGINE_PORT)
    starting.add_argument("--database-url", help="instead of the embedded PostgreSQL")
    starting.add_argument("--online", action="store_true", help="let HuggingFace be reached")
    starting.add_argument(
        "--existing", action="store_true", help="start again on a data folder already set up"
    )
    stopping: argparse.ArgumentParser = commands.add_parser(
        "stop", help="stop a stack and check that it stopped cleanly"
    )
    stopping.add_argument("--out", type=Path, required=True)
    return built


def main(argv: Sequence[str] | None = None) -> int:
    arguments: argparse.Namespace = parser().parse_args(argv)
    try:
        if arguments.command == "start":
            started: Stack = start(arguments)
            print(f"Mesbah {started.version} is up at {started.base_url}")
            return 0
        problems: list[str] = stop(arguments.out)
    except (StackError, OSError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for problem in problems:
        print(f"error: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
