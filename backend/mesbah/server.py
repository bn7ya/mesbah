from __future__ import annotations

import os
import sys
from pathlib import Path

PACKAGE_DIR: Path = Path(__file__).resolve().parent
LOCAL_SETTINGS: str = "config.settings.local"


def server_root() -> Path:
    bundled: Path = PACKAGE_DIR / "_server"
    return bundled if bundled.is_dir() else PACKAGE_DIR.parent


def spa_dir() -> Path | None:
    built: Path = PACKAGE_DIR / "_spa"
    return built if (built / "index.html").is_file() else None


def python_path() -> str:
    existing: str = os.environ.get("PYTHONPATH", "")
    root: str = str(server_root())
    return os.pathsep.join(part for part in (root, existing) if part)


def put_server_on_path() -> None:
    root: str = str(server_root())
    if root not in sys.path:
        sys.path.insert(0, root)
