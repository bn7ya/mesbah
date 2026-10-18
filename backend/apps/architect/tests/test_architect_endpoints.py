from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx2
import pytest
from django.contrib.auth.models import User
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from apps.accounts.repositories import UserRepository
from apps.chat.models import Conversation
from apps.chat.repositories import ConversationRepository, MessageRepository
from apps.members.roles import TRAINERS, VIEWERS
from apps.models.models import HubModel
from apps.models.repositories import HubModelRepository
from apps.projects.models import Project
from apps.projects.repositories import ProjectRepository
from apps.serving.services import EngineClient
from apps.training.models import TrainingRun
from apps.training.repositories import RunRepository
from apps.training.services import RunnerService
from apps.versions.models import ModelVersion

if TYPE_CHECKING:
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

PASSWORD: str = "correct-horse-battery-staple"  # noqa: S105
SMALL_MOE: dict[str, Any] = {
    "family": "moe_decoder",
    "layers": 4,
    "hidden_size": 256,
    "heads": 4,
    "kv_heads": 2,
    "intermediate_size": 512,
    "vocab_size": 32000,
    "context_length": 2048,
    "experts": 8,
    "experts_per_token": 2,
}


def member(role: str) -> APIClient:
    users: UserRepository = UserRepository()
    user: User = users.add_to_group(users.create(username=role, password=PASSWORD), role)
    api: APIClient = APIClient()
    api.force_login(user)
    return api


@pytest.mark.django_db
def test_presets_come_with_their_counts() -> None:
    presets: list[dict[str, Any]] = member(VIEWERS).get("/api/architect/presets/").json()["presets"]

    families: set[str] = {preset["design"]["family"] for preset in presets}
    assert families == {"dense_decoder", "moe_decoder", "encoder_decoder"}
    assert all(preset["counts"]["total"] > 0 for preset in presets)


@pytest.mark.django_db
def test_a_mixture_of_experts_uses_part_of_itself_per_token() -> None:
    response: ApiResponse = member(VIEWERS).post(
        "/api/architect/estimate/", {"design": SMALL_MOE, "seq_len": 512, "batch": 4}, format="json"
    )

    body: dict[str, Any] = response.json()
    assert response.status_code == 200
    assert 0 < body["counts"]["active"] < body["counts"]["total"]
    assert body["counts"]["parts"]["router"] > 0
    assert body["memory"]["training_bytes"] > body["memory"]["weights_bytes"]
    assert body["memory"]["fit"]["verdict"] in {"fits", "tight", "too_large", "cpu_only"}


@pytest.mark.django_db
def test_a_library_tokenizer_counts_the_vocabulary_at_its_size() -> None:
    HubModelRepository().create(
        repo_id="org/tokenizer", status=HubModel.Status.READY, architecture={"vocab_size": 151936}
    )
    viewer: APIClient = member(VIEWERS)

    plain: dict[str, Any] = viewer.post(
        "/api/architect/estimate/", {"design": SMALL_MOE}, format="json"
    ).json()
    sized: dict[str, Any] = viewer.post(
        "/api/architect/estimate/",
        {"design": SMALL_MOE, "tokenizer": "org/tokenizer"},
        format="json",
    ).json()

    assert plain["tokenizer_vocabulary"] is None
    assert sized["tokenizer_vocabulary"] == 151936
    assert sized["design"]["vocab_size"] == 32000
    assert sized["counts"]["parts"]["embeddings"] == 151936 * 256
    assert sized["counts"]["total"] > plain["counts"]["total"]


@pytest.mark.django_db
def test_a_design_that_cannot_be_built_names_the_field() -> None:
    broken: dict[str, Any] = {**SMALL_MOE, "experts_per_token": 9}

    response: ApiResponse = member(VIEWERS).post(
        "/api/architect/estimate/", {"design": broken}, format="json"
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "design_too_many_active_experts"
    assert "experts_per_token" in response.json()["error"]["fields"]


@pytest.mark.django_db
def test_a_trainer_saves_and_changes_a_draft() -> None:
    api: APIClient = member(TRAINERS)
    created: ApiResponse = api.post(
        "/api/architect/drafts/",
        {"name": "Small MoE", "design": SMALL_MOE, "tokenizer": "Qwen/Qwen3-0.6B"},
        format="json",
    )

    changed: ApiResponse = api.patch(
        f"/api/architect/drafts/{created.json()['id']}/",
        {"design": {**SMALL_MOE, "experts": 16}},
        format="json",
    )

    assert created.status_code == 201
    assert changed.json()["design"]["experts"] == 16
    assert changed.json()["counts"]["total"] > created.json()["counts"]["total"]


@pytest.mark.django_db
def test_viewers_cannot_save_drafts() -> None:
    response: ApiResponse = member(VIEWERS).post(
        "/api/architect/drafts/", {"name": "x", "design": SMALL_MOE}, format="json"
    )

    assert response.status_code == 403


@pytest.fixture
def isolated(settings: Settings, tmp_path: Path) -> Iterator[None]:
    settings.MESBAH_DATA_DIR = tmp_path
    settings.MESBAH_FAKE_TRAINER = True

    def stopped(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("no engine", request=request)

    EngineClient.transport = httpx2.MockTransport(stopped)
    yield
    EngineClient.transport = None


def source_project() -> Project:
    model: HubModel = HubModelRepository().create(
        repo_id="org/tiny", status=HubModel.Status.READY, local_path="/models/tiny"
    )
    project: Project = ProjectRepository().create(name="Source", slug="source", base_model=model)
    conversation: Conversation = ConversationRepository().create(project=project)
    messages: MessageRepository = MessageRepository()
    messages.create(conversation=conversation, position=0, role="user", content="Hi")
    messages.create(
        conversation=conversation, position=1, role="assistant", content="Hello", approved=True
    )
    return project


@pytest.mark.django_db
def test_a_design_trained_from_nothing_becomes_a_project_base(isolated: None) -> None:
    api: APIClient = member(TRAINERS)
    tiny: dict[str, Any] = next(
        preset["design"]
        for preset in api.get("/api/architect/presets/").json()["presets"]
        if preset["name"] == "tiny"
    )
    draft: dict[str, Any] = api.post(
        "/api/architect/drafts/",
        {"name": "Tiny MoE", "design": tiny, "tokenizer": "Qwen/Qwen3-0.6B"},
        format="json",
    ).json()
    source: Project = source_project()

    started: ApiResponse = api.post(
        f"/api/architect/drafts/{draft['id']}/train/",
        {"name": "My own model", "corrections_from": [str(source.pk)]},
        format="json",
    )
    RunnerService(poll_seconds=0.05).run(started.json()["run"])

    assert started.status_code == 202
    run: TrainingRun | None = RunRepository().with_project(started.json()["run"])
    assert run is not None and run.status == TrainingRun.Status.COMPLETED, run and run.error_detail
    project: Project | None = ProjectRepository().find(started.json()["project"])
    assert project is not None and project.kind == Project.Kind.SCRATCH
    base: HubModel | None = project.base_model
    assert base is not None
    assert base.origin == HubModel.Origin.TRAINED
    assert base.repo_id == "local/my-own-model"
    assert (Path(base.local_path) / "config.json").exists()
    root: ModelVersion | None = project.active_version
    assert root is not None and root.kind == ModelVersion.Kind.SCRATCH_ROOT
    assert run.version == root


@pytest.mark.django_db
def test_training_a_design_needs_a_tokenizer() -> None:
    api: APIClient = member(TRAINERS)
    draft: dict[str, Any] = api.post(
        "/api/architect/drafts/", {"name": "x", "design": SMALL_MOE}, format="json"
    ).json()

    response: ApiResponse = api.post(
        f"/api/architect/drafts/{draft['id']}/train/",
        {"name": "x", "corrections_from": [str(source_project().pk)]},
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "tokenizer_needed"
