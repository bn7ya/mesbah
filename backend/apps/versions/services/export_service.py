from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.models.models import HubModel
from apps.versions.models import Export, ModelVersion
from apps.versions.repositories import ExportRepository, VersionRepository
from apps.versions.services.errors import ExportNotReady, NotExportable
from mesbah import parts
from mesbah.export.contract import ExportConfig, ExportContractError, ExportStatus
from mesbah.paths import ensure

LOG_TAIL: int = 2000
DEFAULT_OUT_TYPE: str = "f16"
EXPORT_PARTS: tuple[str, ...] = ("torch", "transformers", "peft")
README: str = """# {name}

A LoRA adapter made with Mesbah: only the change to the weights of `{base}`.

- vLLM: `vllm serve {base} --enable-lora --lora-modules {slug}=<this folder>`
- PEFT: `PeftModel.from_pretrained(AutoModelForCausalLM.from_pretrained("{base}"), "<this folder>")`
"""


@dataclass(frozen=True)
class Download:
    path: Path
    filename: str


def exports_dir() -> Path:
    return ensure(Path(settings.MESBAH_DATA_DIR) / "exports")


class ExportService:
    def __init__(self, user: User | AnonymousUser) -> None:
        self.user: User | AnonymousUser = user
        self.exports: ExportRepository = ExportRepository()
        self.versions: VersionRepository = VersionRepository()

    def listing(self, version_id: str) -> QuerySet[Export]:
        return self.exports.of_version(str(self._version(version_id).pk))

    def find(self, export_id: str) -> Export:
        found: Export | None = self.exports.with_version(export_id)
        if found is None:
            raise NotFound
        return found

    def describe(self, export: Export) -> dict[str, Any]:
        downloadable: bool = export.status == Export.Status.READY and export.format != (
            Export.Format.MERGED
        )
        return {
            "id": export.pk,
            "version": export.version_id,
            "format": export.format,
            "out_type": export.out_type,
            "status": export.status,
            "error_code": export.error_code,
            "path": export.path,
            "size_bytes": export.size_bytes,
            "downloadable": downloadable,
            "created_at": export.created_at,
            "finished_at": export.finished_at,
            "created_by": None if export.created_by is None else export.created_by.get_username(),
        }

    @transaction.atomic
    def create(self, version_id: str, format: str, out_type: str = "") -> Export:
        version: ModelVersion = self._version(version_id)
        base: HubModel | None = version.project.base_model
        if base is None or not base.local_path:
            raise NotExportable
        if format != Export.Format.GGUF and version.kind != ModelVersion.Kind.LORA:
            raise NotExportable
        export: Export = self.exports.create(
            created_by=self.user if isinstance(self.user, User) else None,
            version=version,
            format=format,
            out_type=out_type if format == Export.Format.GGUF else "",
        )
        transaction.on_commit(lambda: _enqueue(export))
        return export

    def remove(self, export_id: str) -> None:
        export: Export = self.find(export_id)
        shutil.rmtree(exports_dir() / str(export.pk), ignore_errors=True)
        self.exports.soft_delete(export)

    def download(self, export_id: str) -> Download:
        export: Export = self.find(export_id)
        path: Path = Path(export.path)
        if not self.describe(export)["downloadable"] or not path.is_file():
            raise ExportNotReady
        if export.format != Export.Format.GGUF:
            return Download(path, path.name)
        version: ModelVersion = export.version
        out_type: str = export.out_type or DEFAULT_OUT_TYPE
        return Download(path, f"{version.project.slug}-v{version.number}-{out_type}.gguf")

    def run(self, export_id: str) -> None:
        export: Export | None = self.exports.with_version(export_id)
        if export is None or export.status != Export.Status.QUEUED:
            return
        export = self.exports.update(export, status=Export.Status.RUNNING)
        folder: Path = ensure(exports_dir() / str(export.pk))
        try:
            if export.format == Export.Format.LORA:
                made: Path = self._zip(export, folder)
                self._finish(export, Export.Status.READY, path=str(made), size=made.stat().st_size)
            else:
                self._convert(export, folder)
        except OSError as error:
            self._finish(export, Export.Status.FAILED, code="failed", detail=str(error))

    def _zip(self, export: Export, folder: Path) -> Path:
        version: ModelVersion = export.version
        base: HubModel | None = version.project.base_model
        staging: Path = folder / "adapter"
        shutil.copytree(version.storage_dir, staging, dirs_exist_ok=True)
        (staging / "README.md").write_text(
            README.format(
                name=str(version),
                base="" if base is None else base.repo_id,
                slug=f"{version.project.slug}-v{version.number}",
            ),
            encoding="utf-8",
        )
        archive: str = shutil.make_archive(
            str(folder / f"{version.project.slug}-v{version.number}-lora"), "zip", staging
        )
        shutil.rmtree(staging, ignore_errors=True)
        return Path(archive)

    def _convert(self, export: Export, folder: Path) -> None:
        if not all(parts.installed(name) for name in EXPORT_PARTS):
            self._finish(export, Export.Status.FAILED, code="training_parts_missing")
            return
        version: ModelVersion = export.version
        base: HubModel | None = version.project.base_model
        try:
            config: ExportConfig = ExportConfig.from_json(
                {
                    "kind": export.format,
                    "base_path": "" if base is None else base.local_path,
                    "adapter_path": version.storage_dir
                    if version.kind == ModelVersion.Kind.LORA
                    else None,
                    "output_dir": str(folder / "output"),
                    "status_path": str(folder / "status.json"),
                    "tools_dir": str(ensure(Path(settings.MESBAH_DATA_DIR) / "tools")),
                    "out_type": export.out_type or DEFAULT_OUT_TYPE,
                    "name": f"{version.project.slug}-v{version.number}",
                    "system_prompt": version.project.system_prompt,
                }
            )
        except ExportContractError as error:
            self._finish(export, Export.Status.FAILED, code="failed", detail=str(error))
            return
        config.write(folder / "config.json")
        with (folder / "export.log").open("wb") as log:
            subprocess.run(  # noqa: S603 - Mesbah's own exporter, on a config it wrote
                [sys.executable, "-m", "mesbah.export", "--config", str(folder / "config.json")],
                cwd=settings.BASE_DIR,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
        try:
            status: ExportStatus = ExportStatus.read(folder / "status.json")
        except (OSError, ValueError, ExportContractError):
            tail: str = (folder / "export.log").read_text(errors="replace")[-LOG_TAIL:]
            self._finish(export, Export.Status.FAILED, code="exporter_crashed", detail=tail)
            return
        if status.status == "failed":
            self._finish(
                export,
                Export.Status.FAILED,
                code=status.error_code or "failed",
                detail=status.error_detail,
            )
            return
        self._finish(export, Export.Status.READY, path=status.output or "", size=status.size_bytes)

    def _finish(
        self,
        export: Export,
        status: Export.Status,
        *,
        path: str = "",
        size: int = 0,
        code: str = "",
        detail: str = "",
    ) -> None:
        self.exports.update(
            export,
            status=status,
            path=path,
            size_bytes=size,
            error_code=code[:40],
            error_detail=detail[-LOG_TAIL:],
            finished_at=timezone.now(),
        )

    def _version(self, version_id: str) -> ModelVersion:
        version: ModelVersion | None = self.versions.find(version_id)
        if version is None:
            raise NotFound
        return version


def _enqueue(export: Export) -> None:
    from apps.versions.tasks import convert, package

    task: Any = package if export.format == Export.Format.LORA else convert
    task.delay(str(export.pk))
