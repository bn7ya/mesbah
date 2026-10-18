from __future__ import annotations

import argparse
import io
import os
import socket
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from mesbah import __version__, hardware, parts
from mesbah.launcher import Launcher, Options
from mesbah.paths import DATA_DIR_ENV, data_dir
from mesbah.server import LOCAL_SETTINGS, python_path, server_root

DEFAULT_PORT: int = 8077
GIB: int = 1024**3
CUDA_INDEX: str = "https://download.pytorch.org/whl/cu130"


def main(arguments: Sequence[str] | None = None) -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(line_buffering=True)
    parser: argparse.ArgumentParser = build_parser()
    options: argparse.Namespace = parser.parse_args(arguments)
    if options.data_dir:
        os.environ[DATA_DIR_ENV] = str(Path(options.data_dir).expanduser().resolve())
    command: str = options.command or "start"
    if command == "start":
        return start(options)
    if command == "doctor":
        return doctor(options)
    return manage(options.arguments)


def build_parser() -> argparse.ArgumentParser:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="mesbah",
        description="Mesbah: customize, version and serve language models.",
    )
    parser.add_argument("--version", action="version", version=f"mesbah {__version__}")
    parser.add_argument("--data-dir", help="where Mesbah keeps its data (default: per user)")
    commands: argparse._SubParsersAction[argparse.ArgumentParser] = parser.add_subparsers(
        dest="command"
    )

    start_parser: argparse.ArgumentParser = commands.add_parser("start", help="run Mesbah")
    start_parser.add_argument("--host", default="127.0.0.1", help="address to listen on")
    start_parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="port to listen on")
    start_parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="use this PostgreSQL instead of the built-in one",
    )
    start_parser.add_argument(
        "--no-browser", action="store_true", help="do not open a browser window"
    )

    doctor_parser: argparse.ArgumentParser = commands.add_parser(
        "doctor", help="check this machine and the installation"
    )
    doctor_parser.add_argument("--port", type=int, default=DEFAULT_PORT)

    manage_parser: argparse.ArgumentParser = commands.add_parser(
        "manage", help="run a Django management command against Mesbah's database"
    )
    manage_parser.add_argument("arguments", nargs=argparse.REMAINDER)
    return parser


def start(options: argparse.Namespace) -> int:
    launcher: Launcher = Launcher(
        Options(
            host=getattr(options, "host", "127.0.0.1"),
            port=getattr(options, "port", DEFAULT_PORT),
            data_dir=data_dir(),
            database_url=getattr(options, "database_url", None),
            open_browser=not getattr(options, "no_browser", False),
        )
    )
    return launcher.run()


def manage(arguments: list[str]) -> int:
    launcher: Launcher = Launcher(
        Options(
            host="127.0.0.1",
            port=DEFAULT_PORT,
            data_dir=data_dir(),
            database_url=os.environ.get("DATABASE_URL"),
            open_browser=False,
            owns_database=False,
        )
    )
    try:
        environment: dict[str, str] = launcher.prepare()
        result: subprocess.CompletedProcess[bytes] = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "django", *arguments],
            env=environment,
            cwd=server_root(),
            check=False,
        )
        return result.returncode
    finally:
        launcher.stop()


def doctor(options: argparse.Namespace) -> int:
    machine: hardware.Machine = hardware.machine()
    print(f"Mesbah {__version__} · Python {machine.python} · {machine.system}")
    print(f"Data folder: {data_dir()}")
    print(f"Server code: {server_root()}  (settings {LOCAL_SETTINGS}, path {python_path()})")
    print(f"Memory: {machine.ram_bytes / GIB:.1f} GB · CPU cores: {machine.cpu_count}")
    if machine.gpus:
        for gpu in machine.gpus:
            print(f"GPU {gpu.index}: {gpu.name}, {gpu.memory_bytes / GIB:.1f} GB")
    else:
        print("GPU: no NVIDIA GPU found. Training and chat will use the CPU.")

    installed: tuple[parts.Part, ...] = parts.parts()
    for part in installed:
        print(f"  {part.name:<14} {part.version or 'not installed'}")
    torch: parts.Part = next(part for part in installed if part.name == "torch")
    if torch.version is None:
        print('Training parts are missing. Install them with: pip install "mesbah[train]"')
    elif machine.gpus and torch.cuda is False:
        print("torch is a CPU build. Reinstall it for the GPU:")
        print(f"  pip install --force-reinstall torch --index-url {CUDA_INDEX}")

    port: int = options.port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        busy: bool = probe.connect_ex(("127.0.0.1", port)) == 0
    print(f"Port {port}: {'in use' if busy else 'free'}")
    return 0
