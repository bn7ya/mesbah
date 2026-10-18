from __future__ import annotations

import os
import secrets
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from types import FrameType
from typing import TYPE_CHECKING

from mesbah import __version__
from mesbah.paths import ensure
from mesbah.server import LOCAL_SETTINGS, python_path, server_root, spa_dir

if TYPE_CHECKING:
    from pixeltable_pgserver.postgres_server import PostgresServer

HEALTH_TIMEOUT: float = 90.0
STOP_TIMEOUT: float = 10.0
POLL_SECONDS: float = 1.0
MANAGE_TIMEOUT: float = 600.0
WORKER_THREADS: int = 4


@dataclass(frozen=True)
class Options:
    host: str
    port: int
    data_dir: Path
    database_url: str | None
    open_browser: bool
    owns_database: bool = True


@dataclass
class Launcher:
    options: Options
    processes: dict[str, subprocess.Popen[bytes]] = field(default_factory=dict)
    database: PostgresServer | None = None

    @property
    def address(self) -> str:
        wildcard: set[str] = {"0.0.0.0", "::"}  # noqa: S104 - recognised here, not bound
        host: str = "127.0.0.1" if self.options.host in wildcard else self.options.host
        return f"http://{host}:{self.options.port}"

    def run(self) -> int:
        signal.signal(signal.SIGINT, interrupt)
        signal.signal(signal.SIGTERM, interrupt)
        environment: dict[str, str] = self.prepare()
        try:
            self.manage(environment, "migrate", "--noinput", "-v", "0")
            self.manage(environment, "collectstatic", "--noinput", "-v", "0")
            self.start(environment)
            if not self.wait_until_healthy():
                print("Mesbah did not start. The messages above say why.", file=sys.stderr)
                return 1
            self.announce(environment)
            return self.supervise()
        except KeyboardInterrupt:
            return 0
        finally:
            self.stop()

    def prepare(self) -> dict[str, str]:
        data: Path = ensure(self.options.data_dir)
        url: str = self.options.database_url or self.start_database(data)
        origins: list[str] = [
            self.address,
            f"http://localhost:{self.options.port}",
            f"http://127.0.0.1:{self.options.port}",
        ]
        environment: dict[str, str] = {
            **os.environ,
            "DJANGO_SETTINGS_MODULE": LOCAL_SETTINGS,
            "PYTHONPATH": python_path(),
            "MESBAH_DATA_DIR": str(data),
            "DATABASE_URL": url,
            "DJANGO_SECRET_KEY": os.environ.get("DJANGO_SECRET_KEY") or secret_key(data),
            "DJANGO_ALLOWED_HOSTS": ",".join({self.options.host, "localhost", "127.0.0.1"}),
            "MESBAH_ORIGINS": ",".join(dict.fromkeys(origins)),
        }
        built: Path | None = spa_dir()
        if built is not None:
            environment["MESBAH_SPA_DIR"] = str(built)
        return environment

    def start_database(self, data: Path) -> str:
        from pixeltable_pgserver.postgres_server import get_server

        print("Starting the database…")
        self.database = get_server(data / "postgres", cleanup_mode="stop")
        return str(self.database.get_uri())

    def manage(self, environment: dict[str, str], *arguments: str) -> str:
        result: subprocess.CompletedProcess[bytes] = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "django", *arguments],
            env=environment,
            cwd=server_root(),
            check=True,
            capture_output=True,
            timeout=MANAGE_TIMEOUT,
        )
        return result.stdout.decode().strip()

    def start(self, environment: dict[str, str]) -> None:
        commands: dict[str, list[str]] = {
            "web": [
                sys.executable,
                "-m",
                "uvicorn",
                "config.asgi:application",
                "--host",
                self.options.host,
                "--port",
                str(self.options.port),
                "--log-level",
                "warning",
                "--no-server-header",
            ],
            "worker": [
                sys.executable,
                "-m",
                "celery",
                "-A",
                "config",
                "worker",
                "--queues",
                "default",
                "--pool",
                "threads",
                "--concurrency",
                str(WORKER_THREADS),
                "--hostname",
                "default@%h",
                "--loglevel",
                "warning",
            ],
        }
        for name, command in commands.items():
            self.processes[name] = subprocess.Popen(  # noqa: S603
                command, env=environment, cwd=server_root()
            )

    def wait_until_healthy(self) -> bool:
        deadline: float = time.monotonic() + HEALTH_TIMEOUT
        while time.monotonic() < deadline:
            if any(process.poll() is not None for process in self.processes.values()):
                return False
            try:
                with urllib.request.urlopen(f"{self.address}/api/health/", timeout=2) as reply:  # noqa: S310
                    if reply.status == 200:
                        return True
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(POLL_SECONDS)
        return False

    def announce(self, environment: dict[str, str]) -> None:
        print(f"\nMesbah {__version__} is running at {self.address}")
        print(f"Data: {environment['MESBAH_DATA_DIR']}")
        try:
            code: str = self.manage(environment, "setup_code")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            code = ""
            print("Run `mesbah manage setup_code` to see the first-run setup code.")
        if code and "already" not in code:
            print(f"First run. Open the address above and enter this setup code: {code}")
        print("Press Ctrl+C to stop.\n")
        if self.options.open_browser:
            webbrowser.open(self.address)

    def supervise(self) -> int:
        while True:
            for name, process in self.processes.items():
                if process.poll() is not None:
                    print(f"The {name} process stopped unexpectedly.", file=sys.stderr)
                    return 1
            time.sleep(POLL_SECONDS)

    def stop(self) -> None:
        for process in self.processes.values():
            if process.poll() is None:
                process.terminate()
        for process in self.processes.values():
            try:
                process.wait(timeout=STOP_TIMEOUT)
            except subprocess.TimeoutExpired:
                process.kill()
        self.processes.clear()
        if self.database is not None:
            self.database.cleanup()
            # Handles left by a process that was killed would keep the server alive forever.
            if self.options.owns_database:
                self.database.stop()
            self.database = None


def interrupt(signum: int, frame: FrameType | None) -> None:
    raise KeyboardInterrupt


def secret_key(data: Path) -> str:
    path: Path = data / "secret-key"
    if path.exists():
        return path.read_text().strip()
    key: str = secrets.token_urlsafe(50)
    descriptor: int = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        handle.write(key)
    return key
