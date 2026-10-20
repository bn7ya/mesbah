from __future__ import annotations

import os
from pathlib import Path

import platformdirs

DATA_DIR_ENV: str = "MESBAH_DATA_DIR"


def data_dir() -> Path:
    configured: str = os.environ.get(DATA_DIR_ENV, "").strip()
    root: Path = Path(configured) if configured else Path(platformdirs.user_data_dir("mesbah"))
    return root.expanduser().resolve()


def ensure(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
