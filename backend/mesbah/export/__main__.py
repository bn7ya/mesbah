from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from collections.abc import Sequence
from pathlib import Path

from mesbah.export.contract import ExportConfig, ExportContractError, ExportStatus
from mesbah.export.converter import ConverterUnavailable, converter
from mesbah.export.merge import merge

GGUF_NAME: str = "model.gguf"


def folder_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def modelfile(config: ExportConfig) -> str:
    lines: list[str] = [f"FROM ./{GGUF_NAME}"]
    if config.system_prompt:
        lines.append(f'SYSTEM """{config.system_prompt}"""')
    return "\n".join(lines) + "\n"


def to_gguf(config: ExportConfig, source: Path, output: Path) -> Path:
    script: Path = converter(Path(config.tools_dir))
    target: Path = output / GGUF_NAME
    environment: dict[str, str] = {k: v for k, v in os.environ.items() if k != "NO_LOCAL_GGUF"}
    subprocess.run(  # noqa: S603 - the pinned converter, on paths Mesbah chose
        [sys.executable, "-I", str(script), str(source), "--outfile", str(target)]
        + ["--outtype", config.out_type],
        check=True,
        env=environment,
        cwd=script.parent,
    )
    (output / "Modelfile").write_text(modelfile(config), encoding="utf-8")
    return target


def run(config: ExportConfig) -> ExportStatus:
    output: Path = Path(config.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    base: Path = Path(config.base_path)
    if config.kind == "merged":
        if config.adapter_path is None:
            return ExportStatus("failed", error_code="nothing_to_merge")
        merge(base, Path(config.adapter_path), output)
        return ExportStatus("completed", str(output), folder_size(output))
    with tempfile.TemporaryDirectory(dir=output) as scratch:
        source: Path = base
        if config.adapter_path is not None:
            source = merge(base, Path(config.adapter_path), Path(scratch) / "merged")
        made: Path = to_gguf(config, source, output)
    return ExportStatus("completed", str(made), made.stat().st_size)


def main(argv: Sequence[str] | None = None) -> int:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(prog="python -m mesbah.export")
    parser.add_argument("--config", required=True, type=Path)
    arguments: argparse.Namespace = parser.parse_args(argv)
    try:
        config: ExportConfig = ExportConfig.read(arguments.config)
    except (OSError, ValueError, ExportContractError) as error:
        print(f"the export config cannot be read: {error}", file=sys.stderr)
        return 1
    status: ExportStatus
    try:
        status = run(config)
    except ConverterUnavailable as error:
        status = ExportStatus("failed", error_code="converter_unavailable", error_detail=str(error))
    except subprocess.CalledProcessError as error:
        status = ExportStatus("failed", error_code="conversion_failed", error_detail=str(error))
    except MemoryError as error:
        status = ExportStatus("failed", error_code="out_of_memory", error_detail=str(error))
    except Exception:  # noqa: BLE001 - every failure ends in a status Django can read
        status = ExportStatus("failed", error_code="failed", error_detail=traceback.format_exc())
    if status.status == "failed":
        shutil.rmtree(Path(config.output_dir) / "merged", ignore_errors=True)
    status.write(Path(config.status_path))
    return 0 if status.status == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
