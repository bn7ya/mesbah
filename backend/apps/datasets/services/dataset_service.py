from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from django.contrib.auth.models import AnonymousUser, User
from django.core.cache import cache
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.db.models import QuerySet
from rest_framework.exceptions import APIException, NotFound

from apps.datasets.models import Dataset
from apps.datasets.repositories import DatasetRepository
from apps.datasets.services import storage
from apps.datasets.services.errors import (
    DatasetUnavailable,
    EmptyFile,
    FileTooLarge,
    MissingColumn,
    NotReady,
    UnknownSplit,
    UnsupportedFile,
    UnsupportedFormat,
    UploadMissing,
)
from apps.datasets.services.formats import (
    FORMATS,
    UNSUPPORTED,
    ColumnMap,
    RawRow,
    Sample,
    TrainingRow,
    chosen,
    column_map,
    detect,
    sample,
)
from apps.datasets.services.hub_client import DatasetsHub, FirstRows, HubDataset, SplitRows
from apps.datasets.services.import_service import ImportService
from apps.system.services import SystemService

FEATURED_KEY: str = "datasets:featured"
FEATURED_SECONDS: int = 15 * 60
SEARCH_LIMIT: int = 24
SHOWN_CONVERSATIONS: int = 5
SNIFF_ROWS: int = 100
EXCERPT_CHARS: int = 160
MAX_UPLOAD_BYTES: int = 200 * 1024 * 1024
SYNC_UPLOAD_BYTES: int = 5 * 1024 * 1024
PREFERRED_CONFIG: str = "default"
PREFERRED_SPLIT: str = "train"
ACTIVE: frozenset[str] = frozenset({Dataset.Status.QUEUED, Dataset.Status.IMPORTING})
RETRYABLE: frozenset[str] = frozenset({Dataset.Status.FAILED, Dataset.Status.CANCELLED})


def _excerpt(preview: object) -> str:
    first: object = preview[0] if isinstance(preview, list) and preview else None
    if not isinstance(first, dict):
        return ""
    text: object = first.get("text")
    messages: object = first.get("messages")
    if not isinstance(text, str):
        prompts: list[str] = [
            str(turn.get("content", ""))
            for turn in (messages if isinstance(messages, list) else [])
            if isinstance(turn, dict) and turn.get("role") == "user"
        ]
        text = prompts[0] if prompts else ""
    flat: str = " ".join(str(text).split())
    return flat if len(flat) <= EXCERPT_CHARS else flat[:EXCERPT_CHARS] + "…"


def _grouped(splits: list[SplitRows]) -> list[dict[str, Any]]:
    configs: dict[str, list[dict[str, Any]]] = {}
    for entry in splits:
        configs.setdefault(entry.config, []).append({"name": entry.split, "rows": entry.rows})
    return [{"name": name, "splits": found} for name, found in configs.items()]


def _picked(splits: list[SplitRows], config: str, split: str) -> SplitRows:
    if not splits:
        raise DatasetUnavailable
    if config or split:
        for entry in splits:
            if entry.config == (config or entry.config) and entry.split == (split or entry.split):
                return entry
        raise UnknownSplit
    configs: list[str] = list(dict.fromkeys(entry.config for entry in splits))
    name: str = PREFERRED_CONFIG if PREFERRED_CONFIG in configs else configs[0]
    within: list[SplitRows] = [entry for entry in splits if entry.config == name]
    return next((entry for entry in within if entry.split == PREFERRED_SPLIT), within[0])


def _validated(mapping: ColumnMap, columns: list[str]) -> ColumnMap:
    if mapping.format not in FORMATS:
        raise UnsupportedFormat
    if any(not column for column in mapping.required()):
        raise MissingColumn
    if any(column not in columns for column in mapping.columns()):
        raise MissingColumn
    return mapping


class DatasetService:
    def __init__(self, user: User | AnonymousUser) -> None:
        self.user: User | AnonymousUser = user
        self.datasets: DatasetRepository = DatasetRepository()
        self.system: SystemService = SystemService(user)

    def hub(self) -> DatasetsHub:
        return DatasetsHub(self.system.huggingface_token())

    def library(self) -> QuerySet[Dataset]:
        return self.datasets.library()

    def find(self, dataset_id: str | UUID) -> Dataset:
        row: Dataset | None = self.datasets.find(dataset_id)
        if row is None:
            raise NotFound
        return row

    def describe(self, row: Dataset) -> dict[str, Any]:
        author: User | None = row.created_by
        return {
            "id": row.pk,
            "name": row.name,
            "description": row.description,
            "source": row.source,
            "repo_id": row.repo_id,
            "config_name": row.config_name,
            "split": row.split,
            "file_name": row.file_name,
            "format": row.format,
            "mapping": vars(column_map(row.mapping)) if row.mapping else None,
            "row_limit": row.row_limit,
            "source_rows": row.source_rows,
            "status": row.status,
            "error_code": row.error_code,
            "rows": row.rows,
            "skipped": row.skipped,
            "size_bytes": row.size_bytes,
            "sha256": row.sha256,
            "has_thinking": row.has_thinking,
            "excerpt": _excerpt(row.preview),
            "created_by": "" if author is None else author.get_full_name() or author.username,
            "created_at": row.created_at,
        }

    def search(self, query: str) -> list[dict[str, Any]]:
        return self._listed(self.hub().search(query.strip(), SEARCH_LIMIT))

    def featured(self) -> list[dict[str, Any]]:
        cached: object = cache.get(FEATURED_KEY)
        if isinstance(cached, list):
            return self._listed(cached)
        results: list[HubDataset] = self.hub().search("", SEARCH_LIMIT)
        cache.set(FEATURED_KEY, results, FEATURED_SECONDS)
        return self._listed(results)

    def inspect(
        self, repo_id: str, config: str, split: str, columns: tuple[str, str, str] | None
    ) -> dict[str, Any]:
        hub: DatasetsHub = self.hub()
        about: HubDataset = hub.describe(repo_id)
        splits: list[SplitRows] = hub.splits(repo_id)
        picked: SplitRows = _picked(splits, config, split)
        first: FirstRows = hub.first_rows(repo_id, picked.config, picked.split)
        detected: ColumnMap = detect(first.columns, first.rows)
        mapping: ColumnMap = detected if columns is None else chosen(*columns, detected)
        if mapping.format != UNSUPPORTED:
            _validated(mapping, first.columns)
        tried: Sample = sample(first.rows, mapping)
        return {
            **vars(about),
            "in_library": bool(self.datasets.imported_repos([about.repo_id])),
            "configs": _grouped(splits),
            "config": picked.config,
            "split": picked.split,
            "columns": first.columns,
            "detected": detected.format,
            "mapping": vars(mapping),
            "conversations": [
                {"index": index, **row}
                for index, row in enumerate(tried.rows[:SHOWN_CONVERSATIONS])
            ],
            "sample_rows": len(first.rows),
            "sample_skipped": tried.skipped,
        }

    def start_import(
        self,
        repo_id: str,
        config: str,
        split: str,
        row_limit: int,
        mapping: Mapping[str, object] | None,
    ) -> dict[str, Any]:
        hub: DatasetsHub = self.hub()
        about: HubDataset = hub.describe(repo_id)
        picked: SplitRows = _picked(hub.splits(repo_id), config, split)
        first: FirstRows = hub.first_rows(repo_id, picked.config, picked.split)
        given: ColumnMap = column_map(mapping) if mapping else detect(first.columns, first.rows)
        used: ColumnMap = _validated(given, first.columns)
        with transaction.atomic():
            row: Dataset = self.datasets.create(
                created_by=self._actor(),
                name=about.repo_id,
                source=Dataset.Source.HUB,
                repo_id=about.repo_id,
                config_name=picked.config,
                split=picked.split,
                revision=about.revision,
                mapping=vars(used),
                format=used.format,
                row_limit=row_limit,
                source_rows=picked.rows,
                status=Dataset.Status.QUEUED,
            )
            self._enqueue(row)
        return self.describe(row)

    def upload(self, file: UploadedFile, name: str) -> dict[str, Any]:
        file_name: str = Path(file.name or "").name
        if Path(file_name).suffix.lower() not in storage.UPLOAD_KINDS:
            raise UnsupportedFile
        size: int = file.size or 0
        if size > MAX_UPLOAD_BYTES:
            raise FileTooLarge
        dataset_id: UUID = uuid4()
        staged: Path = storage.incoming_path(str(dataset_id), file_name)
        with staged.open("wb") as handle:
            for chunk in file.chunks():
                handle.write(chunk)
        try:
            mapping: ColumnMap | None = self._sniffed(staged, size)
        except APIException:
            staged.unlink(missing_ok=True)
            raise
        with transaction.atomic():
            row: Dataset = self.datasets.create(
                id=dataset_id,
                created_by=self._actor(),
                name=name.strip() or file_name,
                source=Dataset.Source.UPLOAD,
                file_name=file_name,
                mapping={} if mapping is None else vars(mapping),
                format="" if mapping is None else mapping.format,
                status=Dataset.Status.QUEUED,
            )
            if size >= SYNC_UPLOAD_BYTES:
                self._enqueue(row)
        if size < SYNC_UPLOAD_BYTES:
            ImportService().run(str(dataset_id))
            row = self.find(dataset_id)
        return self.describe(row)

    def update(self, dataset_id: str, changes: Mapping[str, str]) -> dict[str, Any]:
        row: Dataset = self.find(dataset_id)
        fields: dict[str, str] = {key: value.strip() for key, value in changes.items()}
        return self.describe(self.datasets.update(row, **fields) if fields else row)

    def rows(self, dataset_id: str) -> storage.JsonlRows:
        row: Dataset = self.find(dataset_id)
        if row.status != Dataset.Status.READY:
            raise NotReady
        return storage.JsonlRows(str(row.pk), row.rows)

    def cancel(self, dataset_id: str) -> dict[str, Any]:
        row: Dataset = self.find(dataset_id)
        if row.status in ACTIVE:
            row = self.datasets.update(row, cancel_requested=True)
        return self.describe(row)

    def retry(self, dataset_id: str) -> dict[str, Any]:
        row: Dataset = self.find(dataset_id)
        if row.status not in RETRYABLE:
            return self.describe(row)
        if (
            row.source == Dataset.Source.UPLOAD
            and not storage.incoming_path(str(row.pk), row.file_name).exists()
        ):
            raise UploadMissing
        with transaction.atomic():
            row = self.datasets.update(
                row,
                status=Dataset.Status.QUEUED,
                error_code="",
                rows=0,
                skipped=0,
                cancel_requested=False,
            )
            self._enqueue(row)
        return self.describe(row)

    def remove(self, dataset_id: str) -> None:
        row: Dataset = self.find(dataset_id)
        self.datasets.update(row, cancel_requested=True)
        self.datasets.soft_delete(row)
        storage.remove_files(str(row.pk), row.file_name)

    @staticmethod
    def _sniffed(path: Path, size: int) -> ColumnMap | None:
        if path.suffix.lower() == ".json" and size >= SYNC_UPLOAD_BYTES:
            return None
        rows: list[RawRow] = storage.peek_upload(path, SNIFF_ROWS)
        if not rows:
            raise EmptyFile
        mapping: ColumnMap = detect(storage.upload_columns(rows), rows)
        tried: list[TrainingRow] = sample(rows, mapping).rows
        if mapping.format == UNSUPPORTED or not tried:
            raise UnsupportedFormat
        return mapping

    def _listed(self, results: list[HubDataset]) -> list[dict[str, Any]]:
        known: set[str] = self.datasets.imported_repos([result.repo_id for result in results])
        return [
            {**vars(result), "in_library": result.repo_id.lower() in known} for result in results
        ]

    def _actor(self) -> User | None:
        return self.user if isinstance(self.user, User) else None

    @staticmethod
    def _enqueue(row: Dataset) -> None:
        from apps.datasets.tasks import import_dataset

        dataset_id: str = str(row.pk)
        transaction.on_commit(lambda: import_dataset.delay(dataset_id))
