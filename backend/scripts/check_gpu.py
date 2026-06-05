#!/usr/bin/env python
"""Verify the GPU + QLoRA stack end to end.

    python scripts/check_gpu.py

Checks torch/CUDA, the ML imports, and runs a real bitsandbytes 4-bit forward on
the GPU (the bit that actually exercises the Blackwell sm_120 / CUDA-13 path).
Exit code 0 = ready to fine-tune.
"""
from __future__ import annotations

import sys


def main() -> int:
    ok = True
    try:
        import torch
        cuda = torch.cuda.is_available()
        print(f"torch         {torch.__version__}  | cuda={cuda}"
              f"  | {torch.cuda.get_device_name(0) if cuda else 'no gpu'}")
        if not cuda:
            print("  ❌ CUDA not available — check the driver / torch build.")
            return 1
        free, total = torch.cuda.mem_get_info()
        print(f"VRAM          {(total-free)/1e9:.1f} used / {total/1e9:.1f} GB total")
    except Exception as exc:  # noqa: BLE001
        print(f"  ❌ torch import failed: {exc}")
        return 1

    for mod in ("transformers", "peft", "trl", "bitsandbytes", "accelerate", "datasets"):
        try:
            m = __import__(mod)
            print(f"{mod:13} {getattr(m, '__version__', '?')}")
        except Exception as exc:  # noqa: BLE001
            print(f"{mod:13} ❌ MISSING ({exc})")
            ok = False

    try:
        import unsloth  # noqa: F401
        print("unsloth       present (preferred fast path)")
    except Exception:
        print("unsloth       not installed (HF fallback path will be used)")

    if not ok:
        print("\n❌ Install the stack:  pip install -r requirements-ml.txt")
        return 1

    # The real test: a 4-bit linear forward on the GPU.
    try:
        import torch
        import bitsandbytes as bnb
        x = torch.randn(4, 64, device="cuda", dtype=torch.bfloat16)
        lin = bnb.nn.Linear4bit(64, 32, compute_dtype=torch.bfloat16).cuda()
        y = lin(x)
        assert tuple(y.shape) == (4, 32)
        print("\n✅ bitsandbytes 4-bit forward on GPU — WORKING. Ready to fine-tune.")
        return 0
    except Exception as exc:  # noqa: BLE001
        import traceback
        print(f"\n❌ bnb 4-bit forward failed: {exc}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
