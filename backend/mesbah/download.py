from __future__ import annotations

import argparse
import errno
import json
import sys
from collections.abc import Sequence
from pathlib import Path

WEIGHT_FORMATS_TO_SKIP: list[str] = [
    "*.bin",
    "*.pt",
    "*.pth",
    "*.ckpt",
    "*.h5",
    "*.msgpack",
    "*.onnx",
    "*.gguf",
    "*.ot",
    "original/*",
    "onnx/*",
]


def repo_cache_dir(cache_dir: Path, repo_id: str) -> Path:
    return cache_dir / ("models--" + repo_id.replace("/", "--"))


def ignore_patterns(files: Sequence[str]) -> list[str]:
    has_safetensors: bool = any(name.endswith(".safetensors") for name in files)
    return WEIGHT_FORMATS_TO_SKIP if has_safetensors else ["*.gguf", "*.onnx", "onnx/*"]


def download(repo_id: str, revision: str | None, cache_dir: Path, files: Sequence[str]) -> Path:
    from huggingface_hub import snapshot_download

    path: str = str(
        snapshot_download(
            repo_id,
            revision=revision,
            cache_dir=cache_dir,
            ignore_patterns=ignore_patterns(files),
        )
    )
    return Path(path)


def error_code(error: BaseException) -> str:
    from huggingface_hub.errors import GatedRepoError, RepositoryNotFoundError

    if isinstance(error, GatedRepoError):
        return "gated"
    if isinstance(error, RepositoryNotFoundError):
        return "not_found"
    if isinstance(error, OSError) and error.errno == errno.ENOSPC:
        return "disk_full"
    return "network"


def main(arguments: Sequence[str] | None = None) -> int:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(prog="python -m mesbah.download")
    parser.add_argument("repo_id")
    parser.add_argument("--revision")
    parser.add_argument("--cache-dir", required=True)
    parser.add_argument("--file", action="append", default=[])
    options: argparse.Namespace = parser.parse_args(arguments)
    try:
        path: Path = download(
            options.repo_id, options.revision, Path(options.cache_dir), options.file
        )
    except Exception as error:  # noqa: BLE001 - every failure is reported to the caller
        print(json.dumps({"error": error_code(error), "detail": str(error)[:500]}))
        return 1
    print(json.dumps({"path": str(path)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
