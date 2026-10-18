from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import overload

import pyarrow.parquet as pq
from django.conf import settings

from apps.datasets.services.formats import RawRow, TrainingRow
from mesbah.paths import ensure

INDEX_STEP: int = 100
UPLOAD_KINDS: tuple[str, ...] = (".jsonl", ".json", ".csv")

type ReadRow = RawRow | None


def datasets_dir() -> Path:
    return ensure(Path(settings.MESBAH_DATA_DIR) / "datasets")


def incoming_dir() -> Path:
    return ensure(datasets_dir() / "incoming")


def downloads_dir() -> Path:
    return ensure(datasets_dir() / "downloads")


def jsonl_path(dataset_id: str) -> Path:
    return datasets_dir() / f"{dataset_id}.jsonl"


def index_path(dataset_id: str) -> Path:
    return datasets_dir() / f"{dataset_id}.index.json"


def incoming_path(dataset_id: str, file_name: str) -> Path:
    return incoming_dir() / f"{dataset_id}{Path(file_name).suffix.lower()}"


def remove_files(dataset_id: str, file_name: str) -> None:
    for path in (
        jsonl_path(dataset_id),
        index_path(dataset_id),
        jsonl_path(dataset_id).with_suffix(".part"),
        incoming_path(dataset_id, file_name),
    ):
        path.unlink(missing_ok=True)


@dataclass(frozen=True)
class Written:
    rows: int
    size_bytes: int
    sha256: str
    path: Path


class JsonlWriter:
    def __init__(self, dataset_id: str) -> None:
        self.dataset_id: str = dataset_id
        self.target: Path = jsonl_path(dataset_id)
        self.part: Path = self.target.with_suffix(".part")
        self.handle: io.BufferedWriter = self.part.open("wb")
        self.digest: hashlib._Hash = hashlib.sha256()
        self.offsets: list[int] = []
        self.rows: int = 0
        self.size: int = 0

    def write(self, row: TrainingRow) -> None:
        line: bytes = (json.dumps(row, ensure_ascii=False) + "\n").encode()
        if self.rows % INDEX_STEP == 0:
            self.offsets.append(self.size)
        self.handle.write(line)
        self.digest.update(line)
        self.rows += 1
        self.size += len(line)

    def commit(self) -> Written:
        self.handle.close()
        self.part.replace(self.target)
        index_path(self.dataset_id).write_text(json.dumps(self.offsets))
        return Written(
            rows=self.rows, size_bytes=self.size, sha256=self.digest.hexdigest(), path=self.target
        )

    def discard(self) -> None:
        self.handle.close()
        self.part.unlink(missing_ok=True)


class JsonlRows(Sequence[dict[str, object]]):
    def __init__(self, dataset_id: str, count: int) -> None:
        self.path: Path = jsonl_path(dataset_id)
        self.offsets: list[int] = self._offsets(index_path(dataset_id))
        self.total: int = count

    def __len__(self) -> int:
        return self.total

    @overload
    def __getitem__(self, key: int) -> dict[str, object]: ...

    @overload
    def __getitem__(self, key: slice) -> list[dict[str, object]]: ...

    def __getitem__(self, key: int | slice) -> dict[str, object] | list[dict[str, object]]:
        if isinstance(key, int):
            found: list[dict[str, object]] = self._read(key, key + 1)
            if not found:
                raise IndexError(key)
            return found[0]
        start: int
        stop: int
        start, stop, _ = key.indices(self.total)
        return self._read(start, stop)

    def _read(self, start: int, stop: int) -> list[dict[str, object]]:
        if start >= stop or not self.path.exists():
            return []
        block: int = min(start // INDEX_STEP, len(self.offsets) - 1) if self.offsets else 0
        line_number: int = block * INDEX_STEP if self.offsets else 0
        found: list[dict[str, object]] = []
        with self.path.open("rb") as handle:
            handle.seek(self.offsets[block] if self.offsets else 0)
            for raw in handle:
                if line_number >= stop:
                    break
                if line_number >= start:
                    parsed: object = json.loads(raw)
                    found.append(
                        {"index": line_number, **(parsed if isinstance(parsed, dict) else {})}
                    )
                line_number += 1
        return found

    @staticmethod
    def _offsets(path: Path) -> list[int]:
        if not path.exists():
            return []
        loaded: object = json.loads(path.read_text())
        return (
            [value for value in loaded if isinstance(value, int)]
            if isinstance(loaded, list)
            else []
        )


def read_upload(path: Path) -> Iterator[ReadRow]:
    kind: str = path.suffix.lower()
    if kind == ".jsonl":
        yield from _jsonl(path)
    elif kind == ".json":
        yield from _json(path)
    elif kind == ".csv":
        yield from _csv(path)


def peek_upload(path: Path, count: int) -> list[RawRow]:
    found: list[RawRow] = []
    for row in read_upload(path):
        if row is not None:
            found.append(row)
        if len(found) >= count:
            break
    return found


def upload_columns(rows: list[RawRow]) -> list[str]:
    seen: dict[str, None] = {}
    for row in rows:
        for key in row:
            seen.setdefault(str(key), None)
    return list(seen)


def parquet_batches(path: Path, size: int) -> Iterator[list[ReadRow]]:
    table: pq.ParquetFile = pq.ParquetFile(path)
    try:
        for batch in table.iter_batches(batch_size=size):
            rows: list[ReadRow] = [
                row if isinstance(row, dict) else None for row in batch.to_pylist()
            ]
            yield rows
    finally:
        table.close()


def _jsonl(path: Path) -> Iterator[ReadRow]:
    with path.open("rb") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            try:
                parsed: object = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError):
                yield None
                continue
            yield parsed if isinstance(parsed, dict) else None


def _json(path: Path) -> Iterator[ReadRow]:
    try:
        parsed: object = json.loads(path.read_bytes())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    for item in parsed if isinstance(parsed, list) else []:
        yield item if isinstance(item, dict) else None


def _csv(path: Path) -> Iterator[ReadRow]:
    csv.field_size_limit(sys.maxsize)
    with path.open(encoding="utf-8-sig", newline="", errors="replace") as handle:
        for row in csv.DictReader(handle):
            yield {str(key): value for key, value in row.items() if key is not None}
