from __future__ import annotations

import ctypes
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from functools import cache

import psutil

NVIDIA_SMI_TIMEOUT: float = 10.0
MIB: int = 1_048_576


@dataclass(frozen=True)
class Gpu:
    index: int
    name: str
    memory_bytes: int
    compute_capability: str | None


@dataclass(frozen=True)
class Machine:
    gpus: tuple[Gpu, ...]
    driver: str | None
    ram_bytes: int
    cpu_count: int
    system: str
    python: str


def _decoded(value: str | bytes) -> str:
    return value.decode() if isinstance(value, bytes) else value


def _probe_nvml() -> tuple[tuple[Gpu, ...], str | None] | None:
    try:
        import pynvml
    except ImportError:
        return None
    try:
        pynvml.nvmlInit()
    except Exception:  # noqa: BLE001 - no driver or no GPU: the next probe decides
        return None
    try:
        found: list[Gpu] = []
        for index in range(pynvml.nvmlDeviceGetCount()):
            handle: object = pynvml.nvmlDeviceGetHandleByIndex(index)
            capability: str | None
            try:
                major, minor = pynvml.nvmlDeviceGetCudaComputeCapability(handle)
                capability = f"{major}.{minor}"
            except Exception:  # noqa: BLE001 - older drivers do not report it
                capability = None
            found.append(
                Gpu(
                    index=index,
                    name=_decoded(pynvml.nvmlDeviceGetName(handle)),
                    memory_bytes=int(pynvml.nvmlDeviceGetMemoryInfo(handle).total),
                    compute_capability=capability,
                )
            )
        driver: str = _decoded(pynvml.nvmlSystemGetDriverVersion())
        return tuple(found), driver
    except Exception:  # noqa: BLE001 - a half-working driver is treated as none
        return None
    finally:
        pynvml.nvmlShutdown()


def _probe_nvidia_smi() -> tuple[tuple[Gpu, ...], str | None] | None:
    executable: str | None = shutil.which("nvidia-smi")
    if executable is None:
        return None
    try:
        result: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603
            [
                executable,
                "--query-gpu=index,name,memory.total,compute_cap,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=NVIDIA_SMI_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    found: list[Gpu] = []
    driver: str | None = None
    for line in result.stdout.strip().splitlines():
        parts: list[str] = [part.strip() for part in line.split(",")]
        if len(parts) < 3:
            continue
        reported: str = parts[3] if len(parts) > 3 else ""
        capability: str | None = None if reported in {"", "[N/A]"} else reported
        driver = parts[4] if len(parts) > 4 else driver
        found.append(
            Gpu(
                index=int(parts[0]),
                name=parts[1],
                memory_bytes=int(float(parts[2]) * MIB),
                compute_capability=capability,
            )
        )
    return tuple(found), driver


@cache
def gpus() -> tuple[tuple[Gpu, ...], str | None]:
    return _probe_nvml() or _probe_nvidia_smi() or ((), None)


def ram_bytes() -> int:
    try:
        return int(psutil.virtual_memory().total)
    except (OSError, RuntimeError):
        pass
    if sys.platform == "win32":
        return _windows_ram_bytes()
    return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))


def _windows_ram_bytes() -> int:
    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_ulong),
            ("load", ctypes.c_ulong),
            ("total_physical", ctypes.c_ulonglong),
            ("available_physical", ctypes.c_ulonglong),
            ("total_page_file", ctypes.c_ulonglong),
            ("available_page_file", ctypes.c_ulonglong),
            ("total_virtual", ctypes.c_ulonglong),
            ("available_virtual", ctypes.c_ulonglong),
            ("available_extended_virtual", ctypes.c_ulonglong),
        ]

    status: MemoryStatus = MemoryStatus()
    status.length = ctypes.sizeof(MemoryStatus)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))  # type: ignore[attr-defined]
    return int(status.total_physical)


def machine() -> Machine:
    found, driver = gpus()
    return Machine(
        gpus=found,
        driver=driver,
        ram_bytes=ram_bytes(),
        cpu_count=os.cpu_count() or 1,
        system=f"{platform.system()} {platform.release()}".strip(),
        python=platform.python_version(),
    )


def forget() -> None:
    gpus.cache_clear()
