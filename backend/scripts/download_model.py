#!/usr/bin/env python
"""Download a base model from HuggingFace into the local registry.

Usage:
    python scripts/download_model.py Qwen/Qwen3-14B
    python scripts/download_model.py Qwen/Qwen3-8B --dir data/models

This mirrors what the GUI's "download" button does (features/models/service.py),
but is handy for pre-seeding a model from the terminal before the first run.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DIR = BACKEND_DIR / "data" / "models"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo_id", help="HuggingFace repo id, e.g. Qwen/Qwen3-14B")
    ap.add_argument("--dir", default=str(DEFAULT_DIR), help="target models dir")
    ap.add_argument("--token", default=None, help="HF token for gated models")
    args = ap.parse_args()

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("huggingface_hub is not installed. Run: pip install -r requirements.txt", file=sys.stderr)
        return 1

    target = Path(args.dir) / args.repo_id.replace("/", "__")
    print(f"Downloading {args.repo_id} → {target} ...")
    path = snapshot_download(repo_id=args.repo_id, local_dir=str(target), token=args.token)
    print(f"Done: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
