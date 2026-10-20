from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from django.conf import LazySettings
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.accounts.repositories import UserRepository
from apps.members.roles import TRAINERS, VIEWERS
from apps.models.models import HubModel
from apps.models.repositories import HubModelRepository
from apps.models.services import model_service
from apps.models.services.errors import HubUnreachable, ModelGated
from apps.models.services.hub_client import HubDetail, HubResult
from mesbah import hardware

if TYPE_CHECKING:
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

PASSWORD: str = "correct-horse-battery-staple"  # noqa: S105
GIB: int = 1024**3

QWEN: HubResult = HubResult(
    repo_id="Qwen/Qwen3-8B",
    downloads=9_000_000,
    likes=2_100,
    pipeline_tag="text-generation",
    parameters=8_190_735_360,
    license="apache-2.0",
    gated=False,
    model_type="qwen3",
    supports_thinking=True,
)
HIDDEN: HubResult = HubResult(
    repo_id="hf-internal-testing/tiny-random-LlamaForCausalLM",
    downloads=12,
    likes=0,
    pipeline_tag="text-generation",
    parameters=1_000_000,
    license="",
    gated=False,
    model_type="llama",
    supports_thinking=False,
)
DEEPSEEK: HubResult = HubResult(
    repo_id="deepseek-ai/DeepSeek-V3.2",
    downloads=1_000_000,
    likes=900,
    pipeline_tag="text-generation",
    parameters=685_000_000_000,
    license="mit",
    gated=False,
    model_type="deepseek_v32",
    supports_thinking=True,
)
QWEN_CONFIG: dict[str, object] = {
    "architectures": ["Qwen3ForCausalLM"],
    "model_type": "qwen3",
    "num_hidden_layers": 36,
    "hidden_size": 4096,
    "num_attention_heads": 32,
    "num_key_value_heads": 8,
    "max_position_embeddings": 40960,
}
QWEN_FILES: list[tuple[str, int]] = [
    ("config.json", 728),
    ("model-00001-of-00002.safetensors", 9 * GIB),
    ("model-00002-of-00002.safetensors", 7 * GIB),
    ("pytorch_model.bin", 16 * GIB),
    ("tokenizer.json", 11 * 1024**2),
]


class FakeHub:
    def __init__(self, files: list[tuple[str, int]] = QWEN_FILES) -> None:
        self.files: list[tuple[str, int]] = files
        self.looked_up: list[str] = []
        self.hidden: dict[str, HubResult] = {}
        self.found: list[HubResult] = [QWEN]

    def search(self, query: str, task: str, limit: int) -> list[HubResult]:
        return self.found

    def lookup(self, repo_id: str) -> HubResult | None:
        self.looked_up.append(repo_id)
        return self.hidden.get(repo_id)

    def detail(self, repo_id: str) -> HubDetail:
        return HubDetail(
            result=QWEN,
            revision="abc123",
            config=QWEN_CONFIG,
            has_chat_template=True,
            files=self.files,
        )


class DownHub(FakeHub):
    def search(self, query: str, task: str, limit: int) -> list[HubResult]:
        raise HubUnreachable


class GatedHub(FakeHub):
    def detail(self, repo_id: str) -> HubDetail:
        raise ModelGated


def serve(monkeypatch: pytest.MonkeyPatch, hub: FakeHub) -> FakeHub:
    monkeypatch.setattr(model_service.ModelService, "hub", lambda _self: hub)
    return hub


@pytest.fixture(autouse=True)
def isolated(settings: LazySettings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings.MESBAH_DATA_DIR = tmp_path
    monkeypatch.setattr(
        hardware,
        "gpus",
        lambda: ((hardware.Gpu(0, "RTX 5080", 16 * GIB, "12.0"),), "595"),
    )
    monkeypatch.setattr(model_service.ModelService, "hub", lambda _self: FakeHub())
    monkeypatch.setattr(model_service.ModelService, "_enqueue", staticmethod(lambda _row: None))


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def member(role: str) -> User:
    users: UserRepository = UserRepository()
    return users.add_to_group(users.create(username=role, password=PASSWORD), role)


@pytest.mark.django_db
def test_an_empty_search_lists_popular_models(client: APIClient) -> None:
    client.force_login(member(VIEWERS))

    response: ApiResponse = client.get("/api/models/hub/")

    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    assert body["count"] == 1
    result: dict[str, Any] = body["results"][0]
    assert result["repo_id"] == "Qwen/Qwen3-8B"
    assert result["supports_thinking"] is True
    assert result["fit"]["chat"]["verdict"] == "fits"
    assert result["fit"]["chat_full"]["verdict"] == "too_large"
    assert result["in_library"] is None


@pytest.mark.django_db
def test_huggingface_being_down_is_reported(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(model_service.ModelService, "hub", lambda _self: DownHub())
    client.force_login(member(VIEWERS))

    response: ApiResponse = client.get("/api/models/hub/?search=qwen")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "hf_unreachable"


@pytest.mark.django_db
def test_inspecting_explains_the_architecture(client: APIClient) -> None:
    client.force_login(member(VIEWERS))

    response: ApiResponse = client.get("/api/models/hub/inspect/?repo=Qwen/Qwen3-8B")

    body: dict[str, Any] = response.json()
    assert body["family"] == "dense_decoder"
    assert body["architecture"]["context_length"] == 40960
    assert body["downloadable"] is True
    assert body["size_bytes"] == 16 * GIB + 728 + 11 * 1024**2


@pytest.mark.django_db
def test_inspecting_says_whether_the_download_fits_the_disk(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.force_login(member(VIEWERS))
    monkeypatch.setattr("shutil.disk_usage", lambda _p: _Usage(free=500 * GIB))
    roomy: dict[str, Any] = client.get("/api/models/hub/inspect/?repo=Qwen/Qwen3-8B").json()
    monkeypatch.setattr("shutil.disk_usage", lambda _p: _Usage(free=16 * GIB))
    cramped: dict[str, Any] = client.get("/api/models/hub/inspect/?repo=Qwen/Qwen3-8B").json()

    assert (roomy["disk_free_bytes"], roomy["fits_disk"]) == (500 * GIB, True)
    assert (cramped["disk_free_bytes"], cramped["fits_disk"]) == (16 * GIB, False)
    assert cramped["size_bytes"] == roomy["size_bytes"]


@pytest.mark.django_db
def test_a_download_that_just_fits_is_the_one_inspection_calls_a_fit(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    size: int = 16 * GIB + 728 + 11 * 1024**2
    monkeypatch.setattr("shutil.disk_usage", lambda _p: _Usage(free=int(size * 1.05) + 1))
    client.force_login(member(TRAINERS))

    inspected: dict[str, Any] = client.get("/api/models/hub/inspect/?repo=Qwen/Qwen3-8B").json()
    added: ApiResponse = client.post("/api/models/", {"repo_id": "Qwen/Qwen3-8B"}, format="json")

    assert inspected["fits_disk"] is True
    assert added.status_code == 202


@pytest.mark.django_db
def test_a_gated_model_answers_400_not_a_lost_session(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(monkeypatch, GatedHub())
    client.force_login(member(VIEWERS))

    response: ApiResponse = client.get("/api/models/hub/inspect/?repo=org/gated")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "hub_model_gated"


@pytest.mark.django_db
def test_an_exact_repo_id_search_finds_a_hidden_model_and_puts_it_first(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub: FakeHub = serve(monkeypatch, FakeHub())
    hub.hidden[HIDDEN.repo_id] = HIDDEN
    client.force_login(member(VIEWERS))

    body: dict[str, Any] = client.get(f"/api/models/hub/?search={HIDDEN.repo_id}").json()

    assert [row["repo_id"] for row in body["results"]] == [HIDDEN.repo_id, "Qwen/Qwen3-8B"]
    assert body["count"] == 2
    first: dict[str, Any] = body["results"][0]
    assert first["fit"]["chat"]["verdict"] == "fits"
    assert first["in_library"] is None
    assert hub.looked_up == [HIDDEN.repo_id]


@pytest.mark.django_db
def test_an_exact_repo_id_that_cannot_be_looked_up_answers_as_before(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub: FakeHub = serve(monkeypatch, FakeHub())
    client.force_login(member(VIEWERS))

    body: dict[str, Any] = client.get("/api/models/hub/?search=nobody/nothing").json()

    assert [row["repo_id"] for row in body["results"]] == ["Qwen/Qwen3-8B"]
    assert hub.looked_up == ["nobody/nothing"]


@pytest.mark.django_db
def test_a_repo_id_search_already_returned_moves_that_model_first_without_a_lookup(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub: FakeHub = serve(monkeypatch, FakeHub())
    hub.found = [HIDDEN, QWEN]
    client.force_login(member(VIEWERS))

    body: dict[str, Any] = client.get("/api/models/hub/?search=qwen/qwen3-8b").json()

    assert [row["repo_id"] for row in body["results"]] == ["Qwen/Qwen3-8B", HIDDEN.repo_id]
    assert hub.looked_up == []


@pytest.mark.django_db
def test_a_plain_search_does_not_look_anything_up(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub: FakeHub = serve(monkeypatch, FakeHub())
    client.force_login(member(VIEWERS))

    client.get("/api/models/hub/?search=qwen 3")
    client.get("/api/models/hub/?search=qwen")

    assert hub.looked_up == []


@pytest.mark.django_db
def test_without_a_gpu_a_model_beyond_the_ram_is_too_large_not_cpu_only(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hardware, "gpus", lambda: ((), None))
    monkeypatch.setattr(hardware, "ram_bytes", lambda: 16 * GIB)
    hub: FakeHub = serve(monkeypatch, FakeHub())
    hub.found = [DEEPSEEK, QWEN]
    client.force_login(member(VIEWERS))

    results: list[dict[str, Any]] = client.get("/api/models/hub/?search=model").json()["results"]

    huge: dict[str, Any] = results[0]["fit"]
    small: dict[str, Any] = results[1]["fit"]
    assert [huge[use]["verdict"] for use in ("chat", "chat_full", "training")] == ["too_large"] * 3
    assert huge["chat"]["available_bytes"] == 0
    assert huge["chat"]["required_bytes"] > 300 * GIB
    assert small["chat"]["verdict"] == "cpu_only"
    assert small["chat_full"]["verdict"] == "too_large"


@pytest.mark.django_db
def test_a_viewer_cannot_download(client: APIClient) -> None:
    client.force_login(member(VIEWERS))

    response: ApiResponse = client.post("/api/models/", {"repo_id": "Qwen/Qwen3-8B"}, format="json")

    assert response.status_code == 403


@pytest.mark.django_db
def test_a_trainer_adds_a_model_to_the_library(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("shutil.disk_usage", lambda _p: _Usage(free=500 * GIB))
    client.force_login(member(TRAINERS))

    response: ApiResponse = client.post("/api/models/", {"repo_id": "Qwen/Qwen3-8B"}, format="json")

    assert response.status_code == 202
    body: dict[str, Any] = response.json()
    assert body["status"] == "queued"
    assert body["supports_thinking"] is True
    assert body["architecture"]["layers"] == 36
    second: ApiResponse = client.post("/api/models/", {"repo_id": "Qwen/Qwen3-8B"}, format="json")
    assert second.json()["error"]["code"] == "already_in_library"


@pytest.mark.django_db
def test_a_model_that_does_not_fit_on_disk_is_refused(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("shutil.disk_usage", lambda _p: _Usage(free=GIB))
    client.force_login(member(TRAINERS))

    response: ApiResponse = client.post("/api/models/", {"repo_id": "Qwen/Qwen3-8B"}, format="json")

    assert response.status_code == 507
    assert response.json()["error"]["code"] == "disk_full"


@pytest.mark.django_db
def test_a_repository_without_weights_is_refused(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        model_service.ModelService, "hub", lambda _self: FakeHub([("model.Q4_K_M.gguf", GIB)])
    )
    client.force_login(member(TRAINERS))

    response: ApiResponse = client.post("/api/models/", {"repo_id": "Qwen/Qwen3-8B"}, format="json")

    assert response.json()["error"]["code"] == "not_downloadable"


@pytest.mark.django_db
def test_cancelling_and_removing(client: APIClient, tmp_path: Path) -> None:
    trainer: User = member(TRAINERS)
    row: HubModel = HubModelRepository().create(
        created_by=trainer, repo_id="Qwen/Qwen3-8B", status=HubModel.Status.DOWNLOADING
    )
    cached: Path = tmp_path / "hf" / "hub" / "models--Qwen--Qwen3-8B"
    cached.mkdir(parents=True)
    client.force_login(trainer)

    cancelled: ApiResponse = client.post(f"/api/models/{row.pk}/cancel/")
    removed: ApiResponse = client.delete(f"/api/models/{row.pk}/")

    assert cancelled.status_code == 200
    assert removed.status_code == 204
    assert not cached.exists()
    assert client.get("/api/models/").json()["count"] == 0


class _Usage:
    def __init__(self, free: int) -> None:
        self.free: int = free
