from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from django.conf import LazySettings

from apps.datasets.models import Dataset
from apps.datasets.repositories import DatasetRepository
from apps.datasets.services.formats import ColumnMap
from apps.datasets.services.import_service import ImportService
from apps.datasets.tests.hub import FakeServer, serve

THINKS: str = "<think>Count them.</think>Two."


def chats(count: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for number in range(count):
        reply: str = THINKS if number == 1 else f"Reply {number}"
        rows.append(
            {
                "messages": [
                    {"role": "user", "content": f"Question {number}"},
                    {"role": "assistant", "content": "" if number == 2 else reply},
                ]
            }
        )
    return rows


@pytest.fixture(autouse=True)
def data_dir(settings: LazySettings, tmp_path: Path) -> None:
    settings.MESBAH_DATA_DIR = tmp_path


def queued(limit: int | None = 10_000) -> Dataset:
    return DatasetRepository().create(
        name="org/chat",
        source=Dataset.Source.HUB,
        repo_id="org/chat",
        config_name="default",
        split="train",
        mapping=vars(ColumnMap(format="messages", conversation="messages")),
        format="messages",
        row_limit=limit,
        status=Dataset.Status.QUEUED,
    )


def settled(row: Dataset) -> Dataset:
    found: Dataset | None = DatasetRepository().find(row.pk)
    assert found is not None
    return found


@pytest.mark.django_db
def test_an_import_writes_the_training_rows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server: FakeServer = FakeServer(chats(6))
    serve(monkeypatch, server)
    row: Dataset = queued()

    ImportService().run(str(row.pk))

    done: Dataset = settled(row)
    assert (done.status, done.rows, done.skipped) == (Dataset.Status.READY, 5, 1)
    written: Path = tmp_path / "datasets" / f"{row.pk}.jsonl"
    lines: list[str] = written.read_text().splitlines()
    assert json.loads(lines[1]) == {
        "messages": [
            {"role": "user", "content": "Question 1"},
            {"role": "assistant", "content": "Two.", "thinking": "Count them."},
        ]
    }
    assert done.sha256 == hashlib.sha256(written.read_bytes()).hexdigest()
    assert done.size_bytes == written.stat().st_size
    assert done.has_thinking is True
    assert len(done.preview) == 5
    assert done.file_path == str(written)
    assert not list((tmp_path / "datasets" / "downloads").iterdir())
    assert server.requests[0].headers["Authorization"] == "Bearer hf_secret"
    downloaded: list[str] = [str(r.url) for r in server.requests if r.url.host == "huggingface.co"]
    assert len(downloaded) == 1
    assert downloaded[0].endswith("/default/train/0000.parquet")


@pytest.mark.django_db
def test_an_import_stops_at_the_row_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, FakeServer(chats(40)))
    row: Dataset = queued(limit=7)

    ImportService().run(str(row.pk))

    done: Dataset = settled(row)
    assert (done.status, done.rows, done.skipped) == (Dataset.Status.READY, 7, 1)


@pytest.mark.django_db
def test_a_cancelled_import_leaves_no_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    serve(monkeypatch, FakeServer(chats(6)))
    monkeypatch.setattr(DatasetRepository, "should_stop", lambda _self, _id: True)
    row: Dataset = queued()

    ImportService().run(str(row.pk))

    stopped: Dataset = settled(row)
    assert (stopped.status, stopped.cancel_requested) == (Dataset.Status.CANCELLED, False)
    assert not list((tmp_path / "datasets").glob("*.jsonl*"))


@pytest.mark.django_db
def test_a_queued_import_cancelled_before_it_starts(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, FakeServer(chats(6)))
    row: Dataset = DatasetRepository().update(queued(), cancel_requested=True)

    ImportService().run(str(row.pk))

    assert settled(row).status == Dataset.Status.CANCELLED


@pytest.mark.parametrize(("status", "code"), [(401, "gated"), (404, "not_found")])
@pytest.mark.django_db
def test_a_refused_download_fails_with_its_reason(
    monkeypatch: pytest.MonkeyPatch, status: int, code: str
) -> None:
    server: FakeServer = FakeServer(chats(6), parquet_status=status)
    serve(monkeypatch, server)
    row: Dataset = queued()

    ImportService().run(str(row.pk))

    failed: Dataset = settled(row)
    assert (failed.status, failed.error_code) == (Dataset.Status.FAILED, code)


@pytest.mark.django_db
def test_rows_that_never_match_fail_the_import(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, FakeServer([{"messages": [{"role": "user", "content": "Q"}]}]))
    row: Dataset = queued()

    ImportService().run(str(row.pk))

    failed: Dataset = settled(row)
    assert (failed.status, failed.error_code) == (Dataset.Status.FAILED, "unsupported_format")


@pytest.mark.django_db
def test_a_removed_dataset_tells_its_import_to_stop() -> None:
    datasets: DatasetRepository = DatasetRepository()
    row: Dataset = queued()
    assert datasets.should_stop(str(row.pk)) is False

    datasets.soft_delete(row)

    assert datasets.should_stop(str(row.pk)) is True
