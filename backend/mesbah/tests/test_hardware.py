from __future__ import annotations

import subprocess

import pytest

from mesbah import hardware, parts

SMI_OUTPUT: str = (
    "0, NVIDIA GeForce RTX 5080, 16303, 12.0, 595.71.05\n"
    "1, NVIDIA RTX A4000, 16376, [N/A], 595.71.05\n"
)


@pytest.fixture(autouse=True)
def fresh_probe() -> None:
    hardware.forget()


def test_no_driver_and_no_nvidia_smi_means_no_gpus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hardware, "_probe_nvml", lambda: None)
    monkeypatch.setattr("shutil.which", lambda _name: None)

    found, driver = hardware.gpus()

    assert found == ()
    assert driver is None


def test_nvidia_smi_is_read_when_nvml_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hardware, "_probe_nvml", lambda: None)
    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/nvidia-smi")

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, stdout=SMI_OUTPUT, stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)

    found, driver = hardware.gpus()

    assert [gpu.name for gpu in found] == ["NVIDIA GeForce RTX 5080", "NVIDIA RTX A4000"]
    assert found[0].memory_bytes == 16303 * hardware.MIB
    assert found[0].compute_capability == "12.0"
    assert found[1].compute_capability is None
    assert driver == "595.71.05"


def test_machine_always_reports_ram_and_cpus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hardware, "gpus", lambda: ((), None))

    found: hardware.Machine = hardware.machine()

    assert found.ram_bytes > 0
    assert found.cpu_count >= 1


@pytest.mark.parametrize(
    ("version", "cuda"),
    [("2.14.1+cu130", True), ("2.14.1+cpu", False), ("2.14.1", None), (None, None)],
)
def test_torch_build_says_whether_it_can_use_a_gpu(version: str | None, cuda: bool | None) -> None:
    assert parts.Part(name="torch", purpose="training", version=version).cuda is cuda


def test_only_torch_has_a_cuda_flag() -> None:
    assert parts.Part(name="peft", purpose="training", version="0.21.2").cuda is None
