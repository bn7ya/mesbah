from __future__ import annotations

import errno
import logging
import shutil
import time
from collections.abc import Generator
from dataclasses import dataclass, field
from pathlib import Path

from django.contrib.auth.models import AnonymousUser
from rest_framework.exceptions import APIException

from apps.datasets.models import Dataset
from apps.datasets.repositories import DatasetRepository
from apps.datasets.services import storage
from apps.datasets.services.errors import (
    Cancelled,
    DatasetUnavailable,
    EmptyFile,
    NotEnoughDisk,
    UnsupportedFormat,
    UploadMissing,
)
from apps.datasets.services.formats import (
    UNSUPPORTED,
    ColumnMap,
    RawRow,
    TrainingRow,
    Turn,
    column_map,
    detect,
    has_thinking,
    normalise,
)
from apps.datasets.services.hub_client import DatasetsHub, ParquetFile
from apps.datasets.services.storage import ReadRow
from apps.system.services import SystemService

logger: logging.Logger = logging.getLogger(__name__)

BATCH_ROWS: int = 1000
PROGRESS_SECONDS: float = 1.0
PREVIEW_ROWS: int = 5
PREVIEW_CHARS: int = 400
DETECT_ROWS: int = 100
DISK_MARGIN: float = 2.0
FAILURES: dict[str, str] = {
    "hub_dataset_gated": "gated",
    "hub_dataset_not_found": "not_found",
    "hf_unreachable": "hf_unreachable",
    "unsupported_format": "unsupported_format",
    "empty_file": "unsupported_format",
    "disk_full": "disk_full",
}

type Batches = Generator[list[ReadRow], None, None]


@dataclass
class Converted:
    mapping: ColumnMap | None
    skipped: int = 0
    has_thinking: bool = False
    preview: list[TrainingRow] = field(default_factory=list)


def _short(text: str) -> str:
    return text if len(text) <= PREVIEW_CHARS else text[:PREVIEW_CHARS] + "…"


def _previewed(row: TrainingRow) -> TrainingRow:
    if "text" in row:
        return {"text": _short(row["text"])}
    turns: list[Turn] = []
    for turn in row.get("messages", []):
        shortened: Turn = {"role": turn["role"], "content": _short(turn["content"])}
        if "thinking" in turn:
            shortened["thinking"] = _short(turn["thinking"])
        turns.append(shortened)
    return {"messages": turns}


class ImportService:
    def __init__(self) -> None:
        self.datasets: DatasetRepository = DatasetRepository()

    def hub(self) -> DatasetsHub:
        return DatasetsHub(SystemService(AnonymousUser()).huggingface_token())

    def run(self, dataset_id: str) -> None:
        row: Dataset | None = self.datasets.find(dataset_id)
        if row is None or row.status != Dataset.Status.QUEUED:
            return
        if row.cancel_requested:
            self.datasets.update(row, status=Dataset.Status.CANCELLED, cancel_requested=False)
            return
        row = self.datasets.update(
            row, status=Dataset.Status.IMPORTING, error_code="", rows=0, skipped=0
        )
        writer: storage.JsonlWriter = storage.JsonlWriter(dataset_id)
        batches: Batches = self._batches(row)
        try:
            converted: Converted = self._convert(row, batches, writer)
        except Cancelled:
            writer.discard()
            self._finish(dataset_id, Dataset.Status.CANCELLED)
            return
        except APIException as error:
            writer.discard()
            self._finish(
                dataset_id, Dataset.Status.FAILED, FAILURES.get(error.default_code, "failed")
            )
            return
        except OSError as error:
            writer.discard()
            logger.warning("Import %s stopped: %s", dataset_id, error)
            full: bool = error.errno == errno.ENOSPC
            self._finish(dataset_id, Dataset.Status.FAILED, "disk_full" if full else "failed")
            return
        except Exception:
            writer.discard()
            logger.exception("Import %s failed", dataset_id)
            self._finish(dataset_id, Dataset.Status.FAILED, "failed")
            return
        finally:
            batches.close()
        self._settle(dataset_id, writer, converted)

    def _batches(self, row: Dataset) -> Batches:
        if row.source == Dataset.Source.HUB:
            return self._hub_batches(row)
        return self._upload_batches(row)

    def _hub_batches(self, row: Dataset) -> Batches:
        hub: DatasetsHub = self.hub()
        dataset_id: str = str(row.pk)
        files: list[ParquetFile] = hub.parquet_files(row.repo_id, row.config_name, row.split)
        if not files:
            raise DatasetUnavailable
        for number, file in enumerate(files):
            if shutil.disk_usage(storage.datasets_dir()).free < file.size * DISK_MARGIN:
                raise NotEnoughDisk
            target: Path = storage.downloads_dir() / f"{dataset_id}-{number}.parquet"
            try:
                if not hub.download(
                    file.url, target, lambda: not self.datasets.should_stop(dataset_id)
                ):
                    raise Cancelled
                yield from storage.parquet_batches(target, BATCH_ROWS)
            finally:
                target.unlink(missing_ok=True)

    def _upload_batches(self, row: Dataset) -> Batches:
        path: Path = storage.incoming_path(str(row.pk), row.file_name)
        if not path.exists():
            raise UploadMissing
        batch: list[ReadRow] = []
        for item in storage.read_upload(path):
            batch.append(item)
            if len(batch) >= BATCH_ROWS:
                yield batch
                batch = []
        if batch:
            yield batch

    def _convert(self, row: Dataset, batches: Batches, writer: storage.JsonlWriter) -> Converted:
        dataset_id: str = str(row.pk)
        limit: int | None = row.row_limit
        converted: Converted = Converted(mapping=column_map(row.mapping) if row.mapping else None)
        reported: float = time.monotonic()
        for batch in batches:
            mapping: ColumnMap = converted.mapping or self._detected(row, batch)
            converted.mapping = mapping
            for raw in batch:
                if limit is not None and writer.rows >= limit:
                    break
                normalised: TrainingRow | None = None if raw is None else normalise(raw, mapping)
                if normalised is None:
                    converted.skipped += 1
                    continue
                writer.write(normalised)
                if len(converted.preview) < PREVIEW_ROWS:
                    converted.preview.append(_previewed(normalised))
                converted.has_thinking = converted.has_thinking or has_thinking(normalised)
            if self.datasets.should_stop(dataset_id):
                raise Cancelled
            if time.monotonic() - reported >= PROGRESS_SECONDS:
                self.datasets.set_progress(dataset_id, writer.rows, converted.skipped)
                reported = time.monotonic()
            if limit is not None and writer.rows >= limit:
                break
        if writer.rows == 0:
            raise UnsupportedFormat if converted.skipped else EmptyFile
        return converted

    def _detected(self, row: Dataset, batch: list[ReadRow]) -> ColumnMap:
        sample: list[RawRow] = [item for item in batch[:DETECT_ROWS] if item is not None]
        mapping: ColumnMap = detect(storage.upload_columns(sample), sample)
        if mapping.format == UNSUPPORTED:
            raise UnsupportedFormat
        self.datasets.update(row, mapping=vars(mapping), format=mapping.format)
        return mapping

    def _settle(self, dataset_id: str, writer: storage.JsonlWriter, converted: Converted) -> None:
        current: Dataset | None = self.datasets.find(dataset_id)
        if current is None:
            writer.discard()
            return
        written: storage.Written = writer.commit()
        self.datasets.update(
            current,
            status=Dataset.Status.READY,
            error_code="",
            rows=written.rows,
            skipped=converted.skipped,
            size_bytes=written.size_bytes,
            sha256=written.sha256,
            has_thinking=converted.has_thinking,
            preview=converted.preview,
            file_path=str(written.path),
            cancel_requested=False,
        )
        if current.source == Dataset.Source.UPLOAD:
            storage.incoming_path(dataset_id, current.file_name).unlink(missing_ok=True)

    def _finish(self, dataset_id: str, status: str, error_code: str = "") -> None:
        row: Dataset | None = self.datasets.find(dataset_id)
        if row is not None:
            self.datasets.update(row, status=status, error_code=error_code, cancel_requested=False)
