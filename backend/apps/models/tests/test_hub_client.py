from __future__ import annotations

from pathlib import Path

import httpx2
import pytest
from huggingface_hub import HfApi
from huggingface_hub.errors import GatedRepoError, HfHubHTTPError, RepositoryNotFoundError
from huggingface_hub.hf_api import ModelInfo

from apps.models.services.errors import ModelGated, ModelNotFoundOnHub
from apps.models.services.hub_client import HubClient, HubResult

REPO: str = "hf-internal-testing/tiny-random-LlamaForCausalLM"


def model_info(repo_id: str = REPO) -> ModelInfo:
    # ModelInfo takes the API's JSON as untyped keyword arguments.
    return ModelInfo(  # type: ignore[no-untyped-call]
        id=repo_id,
        downloads=12,
        likes=0,
        pipeline_tag="text-generation",
        gated=False,
        tags=["license:mit"],
        config={"model_type": "llama"},
        safetensors={"total": 1_000_000, "parameters": {"F32": 1_000_000}},
    )


def refusing(error: type[HfHubHTTPError], status: int) -> HfHubHTTPError:
    request: httpx2.Request = httpx2.Request("GET", f"https://huggingface.co/api/models/{REPO}")
    return error("refused", response=httpx2.Response(status, request=request))


@pytest.fixture
def hub(tmp_path: Path) -> HubClient:
    return HubClient(None, tmp_path)


def test_a_model_is_looked_up_by_its_exact_repo_id(
    hub: HubClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(HfApi, "model_info", lambda _self, repo_id, **_kw: model_info(repo_id))

    found: HubResult | None = hub.lookup(REPO)

    assert found is not None
    assert (found.repo_id, found.parameters, found.license) == (REPO, 1_000_000, "mit")


@pytest.mark.parametrize(
    "error",
    [
        refusing(RepositoryNotFoundError, 404),
        refusing(GatedRepoError, 401),
        refusing(HfHubHTTPError, 503),
    ],
)
def test_a_lookup_that_fails_finds_nothing(
    hub: HubClient, monkeypatch: pytest.MonkeyPatch, error: HfHubHTTPError
) -> None:
    def fail(_self: HfApi, repo_id: str, **_kw: object) -> ModelInfo:
        raise error

    monkeypatch.setattr(HfApi, "model_info", fail)

    assert hub.lookup(REPO) is None


def test_a_gated_repository_is_gated_not_missing(
    hub: HubClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def gated(_self: HfApi, repo_id: str, **_kw: object) -> ModelInfo:
        raise refusing(GatedRepoError, 401)

    monkeypatch.setattr(HfApi, "model_info", gated)

    with pytest.raises(ModelGated) as caught:
        hub.detail(REPO)

    assert caught.value.status_code == 400
    assert caught.value.default_code == "hub_model_gated"


def test_a_missing_repository_is_missing(hub: HubClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(_self: HfApi, repo_id: str, **_kw: object) -> ModelInfo:
        raise refusing(RepositoryNotFoundError, 404)

    monkeypatch.setattr(HfApi, "model_info", missing)

    with pytest.raises(ModelNotFoundOnHub):
        hub.detail(REPO)
