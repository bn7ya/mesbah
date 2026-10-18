from __future__ import annotations

import pytest

from mesbah import cli, hardware, parts

GIB: int = 1024**3


def test_start_is_what_a_bare_mesbah_does(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[bool] = []

    def fake_start(_options: object) -> int:
        started.append(True)
        return 0

    monkeypatch.setattr(cli, "start", fake_start)

    assert cli.main([]) == 0
    assert started == [True]


def test_doctor_points_a_cpu_build_beside_a_gpu_to_the_cuda_one(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    gpu: hardware.Gpu = hardware.Gpu(
        index=0, name="RTX 5080", memory_bytes=16 * GIB, compute_capability="12.0"
    )
    monkeypatch.setattr(hardware, "gpus", lambda: ((gpu,), "595.71.05"))
    monkeypatch.setattr(
        parts,
        "parts",
        lambda: (parts.Part(name="torch", purpose="training", version="2.14.1+cpu"),),
    )

    assert cli.main(["doctor", "--port", "1"]) == 0

    output: str = capsys.readouterr().out
    assert "GPU 0: RTX 5080, 16.0 GB" in output
    assert cli.CUDA_INDEX in output


def test_doctor_names_the_missing_training_parts(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(hardware, "gpus", lambda: ((), None))
    monkeypatch.setattr(
        parts, "parts", lambda: (parts.Part(name="torch", purpose="training", version=None),)
    )

    cli.main(["doctor", "--port", "1"])

    assert 'pip install "mesbah[train]"' in capsys.readouterr().out
