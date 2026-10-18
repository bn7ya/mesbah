from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings

from mesbah.paths import ensure


def hub_cache_dir() -> Path:
    return ensure(Path(settings.MESBAH_DATA_DIR) / "hf" / "hub")


def directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    total: int = 0
    stack: list[Path] = [path]
    while stack:
        current: Path = stack.pop()
        with os.scandir(current) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    stack.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
    return total
