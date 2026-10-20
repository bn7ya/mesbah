from __future__ import annotations

import re
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import httpx2
from huggingface_hub import HfApi
from huggingface_hub.errors import GatedRepoError, HfHubHTTPError, RepositoryNotFoundError
from huggingface_hub.hf_api import DatasetInfo

from apps.datasets.services.errors import (
    DatasetGated,
    DatasetNotFound,
    DatasetUnavailable,
    HubUnreachable,
)

DATASETS_SERVER: str = "https://datasets-server.huggingface.co"
TIMEOUT_SECONDS: float = 30.0
POPULAR_FILTER: str = "task_categories:text-generation"
SEARCH_FIELDS: list[str] = ["downloads", "likes", "gated", "tags", "description"]
DESCRIPTION_CHARS: int = 240
LANGUAGES_SHOWN: int = 4
CHUNK_BYTES: int = 1024 * 1024
SPACES: re.Pattern[str] = re.compile(r"\s+")


@dataclass(frozen=True)
class HubDataset:
    repo_id: str
    downloads: int
    likes: int
    license: str
    gated: bool
    size_category: str
    languages: list[str] = field(default_factory=list)
    description: str = ""
    revision: str = ""


@dataclass(frozen=True)
class SplitRows:
    config: str
    split: str
    rows: int | None


@dataclass(frozen=True)
class FirstRows:
    columns: list[str]
    rows: list[dict[str, object]]


@dataclass(frozen=True)
class ParquetFile:
    url: str
    size: int


def _tagged(tags: list[str], prefix: str) -> list[str]:
    return [tag.removeprefix(prefix) for tag in tags if tag.startswith(prefix)]


def _snippet(description: str | None) -> str:
    flat: str = SPACES.sub(" ", description or "").strip()
    if len(flat) <= DESCRIPTION_CHARS:
        return flat
    return flat[:DESCRIPTION_CHARS].rsplit(" ", 1)[0] + "…"


def _dataset(info: DatasetInfo) -> HubDataset:
    tags: list[str] = list(info.tags or [])
    licenses: list[str] = _tagged(tags, "license:")
    sizes: list[str] = _tagged(tags, "size_categories:")
    return HubDataset(
        repo_id=info.id,
        downloads=info.downloads or 0,
        likes=info.likes or 0,
        license=licenses[0] if licenses else "",
        gated=bool(info.gated),
        size_category=sizes[0] if sizes else "",
        languages=_tagged(tags, "language:")[:LANGUAGES_SHOWN],
        description=_snippet(info.description),
        revision=info.sha or "",
    )


@contextmanager
def _hub_errors() -> Iterator[None]:
    try:
        yield
    except GatedRepoError as error:
        raise DatasetGated from error
    except RepositoryNotFoundError as error:
        raise DatasetNotFound from error
    except (HfHubHTTPError, httpx2.HTTPError, OSError) as error:
        raise HubUnreachable from error


def _checked(response: httpx2.Response) -> httpx2.Response:
    if response.status_code == httpx2.codes.NOT_FOUND:
        raise DatasetNotFound
    if response.status_code in {httpx2.codes.UNAUTHORIZED, httpx2.codes.FORBIDDEN}:
        raise DatasetGated
    if response.status_code >= httpx2.codes.BAD_REQUEST:
        raise DatasetUnavailable
    return response


class DatasetsHub:
    def __init__(self, token: str | None, transport: httpx2.BaseTransport | None = None) -> None:
        self.api: HfApi = HfApi(token=token)
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"} if token else {}
        self.http: httpx2.Client = httpx2.Client(
            headers=headers,
            timeout=TIMEOUT_SECONDS,
            follow_redirects=True,
            transport=transport,
        )

    def search(self, query: str, limit: int) -> list[HubDataset]:
        return self._listed(query or None, None if query else POPULAR_FILTER, limit)

    def describe(self, repo_id: str) -> HubDataset:
        with _hub_errors():
            info: DatasetInfo = self.api.dataset_info(repo_id)
        return _dataset(info)

    def splits(self, repo_id: str) -> list[SplitRows]:
        listed: object = self._json("/splits", {"dataset": repo_id})
        counts: dict[tuple[str, str], int] = self._counts(repo_id)
        found: list[SplitRows] = []
        for entry in listed.get("splits", []) if isinstance(listed, dict) else []:
            if isinstance(entry, dict):
                key: tuple[str, str] = (str(entry.get("config")), str(entry.get("split")))
                found.append(SplitRows(config=key[0], split=key[1], rows=counts.get(key)))
        return found

    def first_rows(self, repo_id: str, config: str, split: str) -> FirstRows:
        body: object = self._json(
            "/first-rows", {"dataset": repo_id, "config": config, "split": split}
        )
        if not isinstance(body, dict):
            raise DatasetUnavailable
        features: list[object] = list(body.get("features") or [])
        rows: list[object] = list(body.get("rows") or [])
        return FirstRows(
            columns=[str(item["name"]) for item in features if isinstance(item, dict)],
            rows=[
                item["row"]
                for item in rows
                if isinstance(item, dict) and isinstance(item.get("row"), dict)
            ],
        )

    def parquet_files(self, repo_id: str, config: str, split: str) -> list[ParquetFile]:
        body: object = self._json("/parquet", {"dataset": repo_id, "config": config})
        files: list[object] = (
            list(body.get("parquet_files") or []) if isinstance(body, dict) else []
        )
        return [
            ParquetFile(url=str(item["url"]), size=int(item.get("size") or 0))
            for item in files
            if isinstance(item, dict)
            and item.get("url")
            and item.get("config") == config
            and item.get("split") == split
        ]

    def download(self, url: str, target: Path, keep_going: Callable[[], bool]) -> bool:
        checked_at: float = time.monotonic()
        with self._network(), self.http.stream("GET", url) as response:
            _checked(response)
            with target.open("wb") as handle:
                for chunk in response.iter_bytes(CHUNK_BYTES):
                    handle.write(chunk)
                    if time.monotonic() - checked_at >= 1.0:
                        checked_at = time.monotonic()
                        if not keep_going():
                            return False
        return True

    def _listed(self, search: str | None, category: str | None, limit: int) -> list[HubDataset]:
        with _hub_errors():
            found: list[DatasetInfo] = list(
                self.api.list_datasets(
                    search=search,
                    filter=category,
                    sort="downloads",
                    limit=limit,
                    expand=SEARCH_FIELDS,  # type: ignore[arg-type]
                )
            )
        return [_dataset(info) for info in found]

    def _counts(self, repo_id: str) -> dict[tuple[str, str], int]:
        try:
            body: object = self._json("/info", {"dataset": repo_id})
        except DatasetUnavailable:
            return {}
        info: object = body.get("dataset_info") if isinstance(body, dict) else None
        counts: dict[tuple[str, str], int] = {}
        for config, about in info.items() if isinstance(info, dict) else []:
            splits: object = about.get("splits") if isinstance(about, dict) else None
            for split, size in splits.items() if isinstance(splits, dict) else []:
                if isinstance(size, dict) and isinstance(size.get("num_examples"), int):
                    counts[(str(config), str(split))] = size["num_examples"]
        return counts

    def _json(self, path: str, params: dict[str, str]) -> object:
        with self._network():
            response: httpx2.Response = self.http.get(f"{DATASETS_SERVER}{path}", params=params)
        parsed: object = _checked(response).json()
        return parsed

    @staticmethod
    @contextmanager
    def _network() -> Iterator[None]:
        try:
            yield
        except httpx2.HTTPError as error:
            raise HubUnreachable from error
