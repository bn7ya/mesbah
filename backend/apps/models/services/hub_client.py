from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import httpx2
from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.errors import GatedRepoError, HfHubHTTPError, RepositoryNotFoundError
from huggingface_hub.hf_api import ModelInfo

from apps.models.services.errors import HubUnreachable, ModelNotFoundOnHub
from mesbah.sizing import supports_thinking

SEARCH_FIELDS: list[str] = [
    "downloads",
    "likes",
    "pipeline_tag",
    "gated",
    "safetensors",
    "tags",
    "config",
]
DETAIL_FIELDS: list[str] = [*SEARCH_FIELDS, "sha", "cardData"]


@dataclass(frozen=True)
class HubResult:
    repo_id: str
    downloads: int
    likes: int
    pipeline_tag: str
    parameters: int | None
    license: str
    gated: bool
    model_type: str
    supports_thinking: bool


@dataclass(frozen=True)
class HubDetail:
    result: HubResult
    revision: str
    config: dict[str, object]
    has_chat_template: bool
    files: list[tuple[str, int]] = field(default_factory=list)


def _license(info: ModelInfo) -> str:
    for tag in info.tags or []:
        if tag.startswith("license:"):
            return tag.removeprefix("license:")
    return ""


def _chat_template(info: ModelInfo) -> str | None:
    config: dict[str, object] = info.config or {}
    tokenizer: object = config.get("tokenizer_config")
    if not isinstance(tokenizer, dict):
        return None
    template: object = tokenizer.get("chat_template")
    if isinstance(template, list):
        return " ".join(
            str(entry.get("template", "")) for entry in template if isinstance(entry, dict)
        )
    return template if isinstance(template, str) else None


def _result(info: ModelInfo) -> HubResult:
    config: dict[str, object] = info.config or {}
    return HubResult(
        repo_id=info.id,
        downloads=info.downloads or 0,
        likes=info.likes or 0,
        pipeline_tag=info.pipeline_tag or "",
        parameters=info.safetensors.total if info.safetensors else None,
        license=_license(info),
        gated=bool(info.gated),
        model_type=str(config.get("model_type") or ""),
        supports_thinking=supports_thinking(_chat_template(info)),
    )


@contextmanager
def _hub_errors() -> Iterator[None]:
    try:
        yield
    except RepositoryNotFoundError as error:
        raise ModelNotFoundOnHub from error
    except (HfHubHTTPError, httpx2.HTTPError, OSError) as error:
        raise HubUnreachable from error


class HubClient:
    def __init__(self, token: str | None, cache_dir: Path) -> None:
        self.api: HfApi = HfApi(token=token)
        self.token: str | None = token
        self.cache_dir: Path = cache_dir

    def search(self, query: str, task: str, limit: int) -> list[HubResult]:
        with _hub_errors():
            found: list[ModelInfo] = list(
                self.api.list_models(
                    search=query or None,
                    pipeline_tag=task or None,
                    sort="downloads",
                    limit=limit,
                    expand=SEARCH_FIELDS,  # type: ignore[arg-type]
                )
            )
        return [_result(info) for info in found]

    def detail(self, repo_id: str) -> HubDetail:
        with _hub_errors():
            info: ModelInfo = self.api.model_info(repo_id, expand=DETAIL_FIELDS)  # type: ignore[arg-type]
            listing: ModelInfo = self.api.model_info(repo_id, files_metadata=True)
        files: list[tuple[str, int]] = [
            (sibling.rfilename, sibling.size or 0) for sibling in listing.siblings or []
        ]
        return HubDetail(
            result=_result(info),
            revision=info.sha or "",
            config=self._config(repo_id, info.sha),
            has_chat_template=_chat_template(info) is not None,
            files=files,
        )

    def _config(self, repo_id: str, revision: str | None) -> dict[str, object]:
        try:
            path: str = hf_hub_download(
                repo_id,
                "config.json",
                revision=revision,
                cache_dir=self.cache_dir,
                token=self.token,
            )
        except GatedRepoError:
            return {}
        except (HfHubHTTPError, httpx2.HTTPError, OSError):
            return {}
        loaded: object = json.loads(Path(path).read_text())
        return loaded if isinstance(loaded, dict) else {}
