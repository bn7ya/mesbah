from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path

from django.conf import settings

from mesbah.paths import ensure

logger: logging.Logger = logging.getLogger(__name__)

FILE_NAME: str = "setup-code"
ALPHABET: str = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
GROUPS: int = 3
GROUP_LENGTH: int = 4


def code_path() -> Path:
    return ensure(Path(settings.MESBAH_DATA_DIR)) / FILE_NAME


def current_code() -> str:
    path: Path = code_path()
    if path.exists():
        return path.read_text().strip()
    code: str = "-".join(
        "".join(secrets.choice(ALPHABET) for _ in range(GROUP_LENGTH)) for _ in range(GROUPS)
    )
    descriptor: int = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        handle.write(code)
    logger.warning("Mesbah has no accounts yet. The setup code is %s", code)
    return code


def matches(candidate: str) -> bool:
    path: Path = code_path()
    if not path.exists():
        return False
    expected: str = path.read_text().strip()
    return secrets.compare_digest(_normal(candidate), _normal(expected))


def consume() -> bool:
    try:
        code_path().unlink()
    except FileNotFoundError:
        return False
    return True


def _normal(code: str) -> str:
    return code.strip().upper().replace(" ", "").replace("-", "")
