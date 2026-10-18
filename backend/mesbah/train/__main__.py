from __future__ import annotations

import argparse
import json
import signal
import sys
import traceback
from collections.abc import Callable, Sequence
from pathlib import Path
from types import FrameType

from mesbah.train.contract import (
    ContractError,
    EventWriter,
    Failure,
    Metrics,
    Status,
    TrainConfig,
    write_status,
)

type SignalHandler = Callable[[int, FrameType | None], object] | int | signal.Handlers | None


def _interrupt(signum: int, frame: FrameType | None) -> None:
    raise KeyboardInterrupt


def _report_unreadable(path: Path, problem: str) -> None:
    detail: str = f"the training config cannot be read: {problem}"
    print(detail, file=sys.stderr)
    try:
        parsed: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if not isinstance(parsed, dict):
        return
    events: object = parsed.get("events_path")
    status: object = parsed.get("status_path")
    if isinstance(events, str):
        EventWriter(Path(events)).error("failed", detail)
    if isinstance(status, str):
        failure: Failure = Failure(code="failed", detail=detail)
        write_status(Path(status), Status(status="failed", error=failure, metrics=Metrics()))


def _train(config: TrainConfig, fake: bool) -> Status:
    if fake:
        from mesbah.train.fake import run as run_fake

        return run_fake(config)
    from mesbah.train.lora import run as run_lora

    return run_lora(config)


def main(argv: Sequence[str] | None = None) -> int:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(prog="python -m mesbah.train")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--fake", action="store_true")
    options: argparse.Namespace = parser.parse_args(argv)
    config_path: Path = options.config
    fake: bool = options.fake
    try:
        config: TrainConfig = TrainConfig.read(config_path)
    except (OSError, ContractError) as exc:
        _report_unreadable(config_path, str(exc))
        return 1
    previous: SignalHandler = signal.signal(signal.SIGTERM, _interrupt)
    try:
        status: Status = _train(config, fake)
    except Exception:  # noqa: BLE001 - the trainers report their own failures; this is the rest
        traceback.print_exc()
        return 1
    finally:
        signal.signal(signal.SIGTERM, previous)
    return 1 if status.status == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
