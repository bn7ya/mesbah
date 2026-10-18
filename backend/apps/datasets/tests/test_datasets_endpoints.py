from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx2
import pytest
from django.conf import LazySettings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from huggingface_hub import HfApi
from huggingface_hub.hf_api import DatasetInfo
from rest_framework.test import APIClient

from apps.accounts.repositories import UserRepository
from apps.datasets.models import Dataset
from apps.datasets.repositories import DatasetRepository
from apps.datasets.services import dataset_service, storage
from apps.datasets.services.dataset_service import DatasetService
from apps.datasets.services.import_service import ImportService
from apps.datasets.tests.hub import FakeServer, info, jsonl, missing, serve
from apps.members.roles import TRAINERS, VIEWERS

if TYPE_CHECKING:
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

PASSWORD: str = "correct-horse-battery-staple"  # noqa: S105
ALPACA: list[dict[str, object]] = [
    {"instruction": "Translate.", "input": "Good morning", "output": "صباح الخير"},
    {"instruction": "Say hi.", "input": "", "output": "Hi."},
    {"instruction": "Empty.", "input": "", "output": ""},
]


@pytest.fixture(autouse=True)
def isolated(settings: LazySettings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    settings.MESBAH_DATA_DIR = tmp_path
    cache.delete(dataset_service.FEATURED_KEY)
    queued: list[str] = []
    monkeypatch.setattr(
        DatasetService, "_enqueue", staticmethod(lambda row: queued.append(str(row.pk)))
    )
    return queued


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def member(role: str) -> User:
    users: UserRepository = UserRepository()
    return users.add_to_group(users.create(username=role, password=PASSWORD), role)


def upload(client: APIClient, name: str, content: bytes) -> ApiResponse:
    file: SimpleUploadedFile = SimpleUploadedFile(name, content)
    return client.post("/api/datasets/upload/", {"file": file}, format="multipart")


def ready(rows: int) -> Dataset:
    lines: list[dict[str, object]] = [{"text": f"Line {number}"} for number in range(rows)]
    row: Dataset = DatasetRepository().create(
        name="lines",
        source=Dataset.Source.UPLOAD,
        file_name="lines.jsonl",
        status=Dataset.Status.QUEUED,
    )
    staged: Path = storage.incoming_path(str(row.pk), row.file_name)
    staged.write_bytes(jsonl(lines))
    ImportService().run(str(row.pk))
    return row


@pytest.mark.django_db
def test_an_empty_search_lists_popular_datasets(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: dict[str, Any] = {}

    def list_datasets(_self: HfApi, **kwargs: Any) -> list[DatasetInfo]:
        asked.update(kwargs)
        return [info("org/chat")]

    monkeypatch.setattr(HfApi, "list_datasets", list_datasets)
    client.force_login(member(VIEWERS))

    response: ApiResponse = client.get("/api/datasets/hub/")

    assert response.status_code == 200
    result: dict[str, Any] = response.json()["results"][0]
    assert result == {
        "repo_id": "org/chat",
        "downloads": 12_000,
        "likes": 340,
        "license": "apache-2.0",
        "gated": False,
        "size_category": "1K<n<10K",
        "languages": ["ar", "en"],
        "description": "Dataset Card for Chat Conversations to learn from.",
        "in_library": False,
    }
    assert (asked["filter"], asked["sort"]) == ("task_categories:text-generation", "downloads")


@pytest.mark.django_db
def test_a_search_sends_the_words(client: APIClient, monkeypatch: pytest.MonkeyPatch) -> None:
    asked: dict[str, Any] = {}

    def list_datasets(_self: HfApi, **kwargs: Any) -> list[DatasetInfo]:
        asked.update(kwargs)
        return [info("org/chat")]

    monkeypatch.setattr(HfApi, "list_datasets", list_datasets)
    DatasetRepository().create(
        name="x", source=Dataset.Source.HUB, repo_id="org/chat", status=Dataset.Status.READY
    )
    client.force_login(member(VIEWERS))

    response: ApiResponse = client.get("/api/datasets/hub/?search=arabic")

    assert (asked["search"], asked["filter"]) == ("arabic", None)
    assert response.json()["results"][0]["in_library"] is True


@pytest.mark.django_db
def test_huggingface_being_down_is_reported(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def list_datasets(_self: HfApi, **_: Any) -> list[DatasetInfo]:
        raise httpx2.ConnectError("down")

    monkeypatch.setattr(HfApi, "list_datasets", list_datasets)
    client.force_login(member(VIEWERS))

    response: ApiResponse = client.get("/api/datasets/hub/?search=chat")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "hf_unreachable"


@pytest.mark.django_db
def test_inspecting_shows_the_rows_as_conversations(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(monkeypatch, FakeServer(ALPACA))
    client.force_login(member(VIEWERS))

    response: ApiResponse = client.get("/api/datasets/hub/inspect/?repo=org/chat")

    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    assert (body["config"], body["split"]) == ("default", "train")
    assert body["configs"] == [
        {"name": "default", "splits": [{"name": "train", "rows": 3}, {"name": "test", "rows": 3}]}
    ]
    assert body["columns"] == ["instruction", "input", "output"]
    assert (body["detected"], body["mapping"]["prompt"]) == ("instruction", "instruction")
    assert (body["sample_rows"], body["sample_skipped"]) == (3, 1)
    assert body["conversations"][0] == {
        "index": 0,
        "messages": [
            {"role": "user", "content": "Translate.\n\nGood morning", "thinking": ""},
            {"role": "assistant", "content": "صباح الخير", "thinking": ""},
        ],
        "text": "",
    }


@pytest.mark.django_db
def test_chosen_columns_change_how_rows_are_read(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(monkeypatch, FakeServer([{"title": "Q", "body": "A", "notes": "why"}]))
    client.force_login(member(VIEWERS))

    detected: ApiResponse = client.get("/api/datasets/hub/inspect/?repo=org/chat")
    chosen: ApiResponse = client.get(
        "/api/datasets/hub/inspect/?repo=org/chat&prompt=title&reply=body&thinking=notes"
    )
    wrong: ApiResponse = client.get("/api/datasets/hub/inspect/?repo=org/chat&prompt=x&reply=body")

    assert detected.json()["detected"] == "unsupported"
    assert detected.json()["conversations"] == []
    assert chosen.json()["mapping"]["format"] == "prompt_completion"
    assert chosen.json()["conversations"][0]["messages"][1]["thinking"] == "why"
    assert wrong.json()["error"]["code"] == "missing_column"


@pytest.mark.django_db
def test_an_unknown_split_is_refused(client: APIClient, monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, FakeServer(ALPACA))
    client.force_login(member(VIEWERS))

    response: ApiResponse = client.get("/api/datasets/hub/inspect/?repo=org/chat&split=nope")

    assert response.json()["error"]["code"] == "unknown_split"


@pytest.mark.django_db
def test_a_gated_dataset_says_so(client: APIClient, monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, FakeServer(ALPACA, status=401), gated=True)
    client.force_login(member(VIEWERS))

    response: ApiResponse = client.get("/api/datasets/hub/inspect/?repo=org/chat")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "hub_dataset_gated"


@pytest.mark.django_db
def test_a_missing_dataset_says_so(client: APIClient, monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, FakeServer(ALPACA))
    missing(monkeypatch)
    client.force_login(member(VIEWERS))

    response: ApiResponse = client.get("/api/datasets/hub/inspect/?repo=nobody/nothing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "hub_dataset_not_found"


@pytest.mark.django_db
def test_a_viewer_cannot_change_the_library(client: APIClient) -> None:
    viewer: User = member(VIEWERS)
    row: Dataset = DatasetRepository().create(
        name="x", source=Dataset.Source.HUB, status=Dataset.Status.FAILED
    )
    client.force_login(viewer)

    attempts: list[ApiResponse] = [
        client.post("/api/datasets/", {"repo_id": "org/chat"}, format="json"),
        upload(client, "rows.jsonl", b'{"text": "x"}\n'),
        client.patch(f"/api/datasets/{row.pk}/", {"name": "y"}, format="json"),
        client.delete(f"/api/datasets/{row.pk}/"),
        client.post(f"/api/datasets/{row.pk}/retry/"),
        client.post(f"/api/datasets/{row.pk}/cancel/"),
    ]

    assert [attempt.status_code for attempt in attempts] == [403] * 6
    assert client.get("/api/datasets/").json()["count"] == 1


@pytest.mark.django_db
def test_a_trainer_imports_a_split(
    client: APIClient, monkeypatch: pytest.MonkeyPatch, isolated: list[str]
) -> None:
    serve(monkeypatch, FakeServer(ALPACA))
    client.force_login(member(TRAINERS))

    response: ApiResponse = client.post(
        "/api/datasets/",
        {"repo_id": "org/chat", "split": "test", "row_limit": 200},
        format="json",
    )

    assert response.status_code == 202
    body: dict[str, Any] = response.json()
    assert (body["status"], body["name"], body["config_name"], body["split"]) == (
        "queued",
        "org/chat",
        "default",
        "test",
    )
    assert (body["format"], body["row_limit"], body["source_rows"]) == ("instruction", 200, 3)
    assert body["created_by"] == "trainers"
    assert isolated == [body["id"]]


@pytest.mark.django_db
def test_an_import_takes_the_chosen_columns(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(monkeypatch, FakeServer([{"title": "Q", "body": "A"}]))
    client.force_login(member(TRAINERS))
    mapping: dict[str, str] = {"format": "prompt_completion", "prompt": "title", "reply": "body"}

    refused: ApiResponse = client.post("/api/datasets/", {"repo_id": "org/chat"}, format="json")
    taken: ApiResponse = client.post(
        "/api/datasets/", {"repo_id": "org/chat", "mapping": mapping}, format="json"
    )

    assert refused.json()["error"]["code"] == "unsupported_format"
    assert taken.status_code == 202
    assert taken.json()["mapping"]["prompt"] == "title"


@pytest.mark.django_db
def test_a_small_jsonl_upload_is_ready_at_once(client: APIClient, tmp_path: Path) -> None:
    client.force_login(member(TRAINERS))
    rows: list[dict[str, object]] = [
        {"messages": [{"role": "user", "content": "Q"}, {"role": "assistant", "content": "A"}]},
        {"messages": [{"role": "user", "content": "Q"}]},
    ]

    response: ApiResponse = upload(client, "chats.jsonl", jsonl(rows) + b"not json\n")

    assert response.status_code == 201
    body: dict[str, Any] = response.json()
    assert (body["status"], body["rows"], body["skipped"]) == ("ready", 1, 2)
    assert (body["name"], body["source"], body["format"]) == ("chats.jsonl", "upload", "messages")
    assert body["excerpt"] == "Q"
    assert not list((tmp_path / "datasets" / "incoming").iterdir())


@pytest.mark.django_db
def test_a_csv_upload_maps_its_columns(client: APIClient) -> None:
    client.force_login(member(TRAINERS))
    sheet: io.StringIO = io.StringIO()
    writer: Any = csv.writer(sheet)
    writer.writerows([["question", "answer"], ["ما اسمك؟", "مصباح"], ["2+2?", "4"]])

    response: ApiResponse = upload(client, "pairs.csv", sheet.getvalue().encode())

    body: dict[str, Any] = response.json()
    assert (body["format"], body["rows"]) == ("prompt_completion", 2)


@pytest.mark.django_db
def test_a_json_list_upload(client: APIClient) -> None:
    client.force_login(member(TRAINERS))

    response: ApiResponse = upload(client, "alpaca.json", json.dumps(ALPACA).encode())

    body: dict[str, Any] = response.json()
    assert (body["format"], body["rows"], body["skipped"]) == ("instruction", 2, 1)


@pytest.mark.django_db
def test_a_large_upload_is_read_in_the_background(
    client: APIClient, monkeypatch: pytest.MonkeyPatch, isolated: list[str]
) -> None:
    monkeypatch.setattr(dataset_service, "SYNC_UPLOAD_BYTES", 10)
    client.force_login(member(TRAINERS))

    response: ApiResponse = upload(client, "lines.jsonl", jsonl([{"text": "One"}, {"text": "Two"}]))

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    ImportService().run(isolated[0])
    assert client.get(f"/api/datasets/{isolated[0]}/").json()["rows"] == 2


@pytest.mark.django_db
def test_uploads_that_cannot_be_read_are_refused(
    client: APIClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(dataset_service, "MAX_UPLOAD_BYTES", 20)
    client.force_login(member(TRAINERS))

    large: ApiResponse = upload(client, "big.jsonl", b'{"text": "' + b"x" * 40 + b'"}\n')
    kind: ApiResponse = upload(client, "rows.parquet", b"PAR1")
    layout: ApiResponse = upload(client, "rows.jsonl", b'{"a": 1}\n')
    empty: ApiResponse = upload(client, "rows.csv", b"")

    assert (large.status_code, large.json()["error"]["code"]) == (413, "file_too_large")
    assert kind.json()["error"]["code"] == "unsupported_file"
    assert layout.json()["error"]["code"] == "unsupported_format"
    assert empty.json()["error"]["code"] == "empty_file"
    assert client.get("/api/datasets/").json()["count"] == 0
    assert not list((tmp_path / "datasets" / "incoming").iterdir())


@pytest.mark.django_db
def test_rows_are_paged_by_line(client: APIClient) -> None:
    client.force_login(member(VIEWERS))
    row: Dataset = ready(250)

    first: ApiResponse = client.get(f"/api/datasets/{row.pk}/rows/?page_size=10")
    third: ApiResponse = client.get(f"/api/datasets/{row.pk}/rows/?page=3&page_size=100")

    assert first.json()["count"] == 250
    assert first.json()["results"][0] == {"index": 0, "messages": [], "text": "Line 0"}
    assert first.json()["next"] is not None
    assert [entry["index"] for entry in third.json()["results"]] == list(range(200, 250))
    assert third.json()["results"][-1]["text"] == "Line 249"
    assert third.json()["next"] is None


@pytest.mark.django_db
def test_rows_wait_for_the_import(client: APIClient) -> None:
    client.force_login(member(VIEWERS))
    row: Dataset = DatasetRepository().create(
        name="x", source=Dataset.Source.HUB, status=Dataset.Status.IMPORTING
    )

    response: ApiResponse = client.get(f"/api/datasets/{row.pk}/rows/")

    assert (response.status_code, response.json()["error"]["code"]) == (409, "dataset_not_ready")


@pytest.mark.django_db
def test_renaming_and_describing(client: APIClient) -> None:
    client.force_login(member(TRAINERS))
    row: Dataset = ready(2)

    response: ApiResponse = client.patch(
        f"/api/datasets/{row.pk}/",
        {"name": "  Greetings ", "description": "Short hellos."},
        format="json",
    )

    assert (response.json()["name"], response.json()["description"]) == (
        "Greetings",
        "Short hellos.",
    )


@pytest.mark.django_db
def test_removing_deletes_the_file(client: APIClient, tmp_path: Path) -> None:
    client.force_login(member(TRAINERS))
    row: Dataset = ready(2)
    assert (tmp_path / "datasets" / f"{row.pk}.jsonl").exists()

    response: ApiResponse = client.delete(f"/api/datasets/{row.pk}/")

    assert response.status_code == 204
    assert not (tmp_path / "datasets" / f"{row.pk}.jsonl").exists()
    assert client.get("/api/datasets/").json()["count"] == 0


@pytest.mark.django_db
def test_cancelling_and_retrying(client: APIClient, isolated: list[str]) -> None:
    client.force_login(member(TRAINERS))
    row: Dataset = DatasetRepository().create(
        name="org/chat", source=Dataset.Source.HUB, repo_id="org/chat", status=Dataset.Status.QUEUED
    )

    cancelled: ApiResponse = client.post(f"/api/datasets/{row.pk}/cancel/")
    ImportService().run(str(row.pk))
    retried: ApiResponse = client.post(f"/api/datasets/{row.pk}/retry/")

    assert cancelled.status_code == 200
    assert DatasetRepository().get(row.pk).cancel_requested is False
    assert (retried.status_code, retried.json()["status"]) == (202, "queued")
    assert isolated == [str(row.pk)]
