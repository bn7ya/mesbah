from __future__ import annotations

import io
import json
from dataclasses import dataclass, field

import httpx2
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from huggingface_hub import HfApi
from huggingface_hub.errors import RepositoryNotFoundError
from huggingface_hub.hf_api import DatasetInfo

from apps.datasets.services.dataset_service import DatasetService
from apps.datasets.services.hub_client import DatasetsHub
from apps.datasets.services.import_service import ImportService

PARQUET_ROOT: str = "https://huggingface.co/datasets/org/chat/resolve/refs%2Fconvert%2Fparquet"


def parquet_bytes(rows: list[dict[str, object]]) -> bytes:
    sink: io.BytesIO = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(rows), sink)
    return sink.getvalue()


def info(repo_id: str = "org/chat", gated: bool = False) -> DatasetInfo:
    # DatasetInfo takes the API's JSON as untyped keyword arguments.
    return DatasetInfo(  # type: ignore[no-untyped-call]
        id=repo_id,
        downloads=12_000,
        likes=340,
        gated="manual" if gated else False,
        tags=["license:apache-2.0", "size_categories:1K<n<10K", "language:ar", "language:en"],
        description="\n\tDataset Card for Chat\n\n Conversations   to learn from. ",
        sha="abc123",
    )


@dataclass
class FakeServer:
    rows: list[dict[str, object]]
    configs: dict[str, list[str]] = field(default_factory=lambda: {"default": ["train", "test"]})
    status: int = 200
    parquet_status: int = 200
    requests: list[httpx2.Request] = field(default_factory=list)

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        path: str = request.url.path
        if request.url.host == "huggingface.co":
            if self.parquet_status != 200:
                return httpx2.Response(self.parquet_status)
            return httpx2.Response(200, content=parquet_bytes(self.rows))
        if self.status != 200:
            return httpx2.Response(self.status, json={"error": "nope"})
        if path == "/splits":
            return httpx2.Response(200, json={"splits": self._splits()})
        if path == "/info":
            return httpx2.Response(200, json={"dataset_info": self._info()})
        if path == "/first-rows":
            return httpx2.Response(200, json=self._first_rows())
        if path == "/parquet":
            return httpx2.Response(200, json={"parquet_files": self._parquet()})
        return httpx2.Response(404)

    def hub(self) -> DatasetsHub:
        return DatasetsHub("hf_secret", transport=httpx2.MockTransport(self.handle))

    def _splits(self) -> list[dict[str, str]]:
        return [
            {"dataset": "org/chat", "config": config, "split": split}
            for config, splits in self.configs.items()
            for split in splits
        ]

    def _info(self) -> dict[str, object]:
        return {
            config: {"splits": {split: {"num_examples": len(self.rows)} for split in splits}}
            for config, splits in self.configs.items()
        }

    def _parquet(self) -> list[dict[str, object]]:
        return [
            {
                "config": config,
                "split": split,
                "url": f"{PARQUET_ROOT}/{config}/{split}/0000.parquet",
            }
            for config, splits in self.configs.items()
            for split in splits
        ]

    def _first_rows(self) -> dict[str, object]:
        names: list[str] = list(dict.fromkeys(key for row in self.rows for key in row))
        return {
            "features": [{"feature_idx": i, "name": name} for i, name in enumerate(names)],
            "rows": [{"row_idx": i, "row": row} for i, row in enumerate(self.rows[:100])],
        }


def serve(monkeypatch: pytest.MonkeyPatch, server: FakeServer, gated: bool = False) -> None:
    def hub(_self: object) -> DatasetsHub:
        return server.hub()

    monkeypatch.setattr(DatasetService, "hub", hub)
    monkeypatch.setattr(ImportService, "hub", hub)
    monkeypatch.setattr(HfApi, "dataset_info", lambda _self, repo_id, **_: info(repo_id, gated))


def missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def dataset_info(_self: HfApi, repo_id: str, **_: object) -> DatasetInfo:
        url: str = f"https://huggingface.co/api/datasets/{repo_id}"
        response: httpx2.Response = httpx2.Response(404, request=httpx2.Request("GET", url))
        raise RepositoryNotFoundError("missing", response=response)

    monkeypatch.setattr(HfApi, "dataset_info", dataset_info)


def jsonl(rows: list[dict[str, object]]) -> bytes:
    return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode()
