from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

import uvicorn

from mesbah.runtime.app import create_app
from mesbah.runtime.engine import Engine

TOKEN_VARIABLE: str = "MESBAH_RUNTIME_TOKEN"  # noqa: S105 - the variable's name, not a secret
DEFAULT_HOST: str = "127.0.0.1"
DEFAULT_PORT: int = 8078
SHUTDOWN_GRACE_SECONDS: int = 5


def main(argv: Sequence[str] | None = None) -> int:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="python -m mesbah.runtime",
        description="Mesbah's built-in engine: one base model and its versions, served over an "
        "OpenAI-compatible API.",
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    arguments: argparse.Namespace = parser.parse_args(argv)
    token: str | None = os.environ.get(TOKEN_VARIABLE) or None
    uvicorn.run(
        create_app(Engine(), token),
        host=arguments.host,
        port=arguments.port,
        timeout_graceful_shutdown=SHUTDOWN_GRACE_SECONDS,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
