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
from apps.chat.models import Conversation, Message
from apps.chat.repositories import ConversationRepository, MessageRepository
from apps.datasets.models import Dataset
from apps.datasets.repositories import DatasetRepository
from apps.members.roles import TRAINERS, VIEWERS
from apps.models.models import HubModel
from apps.models.repositories import HubModelRepository
from apps.projects.models import Project
from apps.projects.repositories import ProjectRepository
from apps.serving.services import DeploymentService, EngineClient
from apps.serving.services.errors import EngineFailed
from apps.training.models import TrainingRun
from apps.training.repositories import RunRepository
from apps.training.services import RunnerService, TrainingService
from apps.versions.models import ModelVersion
from apps.versions.services import VersionService

if TYPE_CHECKING:
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

PASSWORD: str = "correct-horse-battery-staple"  # noqa: S105


@pytest.fixture(autouse=True)
def isolated(settings: Settings, tmp_path: Path) -> Iterator[None]:
    settings.MESBAH_DATA_DIR = tmp_path
    settings.MESBAH_FAKE_TRAINER = True

    def stopped(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("no engine", request=request)

    EngineClient.transport = httpx2.MockTransport(stopped)
    yield
    EngineClient.transport = None


@pytest.fixture
def trainer(db: None) -> User:
    users: UserRepository = UserRepository()
    return users.add_to_group(users.create(username="tariq", password=PASSWORD), TRAINERS)


@pytest.fixture
def client(trainer: User) -> APIClient:
    api: APIClient = APIClient()
    api.force_login(trainer)
    return api


@pytest.fixture
def project(trainer: User) -> Project:
    model: HubModel = HubModelRepository().create(
        repo_id="org/tiny",
        status=HubModel.Status.READY,
        local_path="/models/org-tiny",
        parameters=2_000_000,
        size_bytes=8_000_000,
    )
    owner: Project = ProjectRepository().create(
        name="Tiny", slug="tiny", base_model=model, system_prompt="Answer briefly."
    )
    VersionService(trainer).create_root(owner)
    found: Project | None = ProjectRepository().find(str(owner.pk))
    assert found is not None
    return found


def approve_a_reply(project: Project, thinking: str = "Recall the capital.") -> Message:
    conversation: Conversation = ConversationRepository().create(project=project, title="Paris")
    messages: MessageRepository = MessageRepository()
    messages.create(conversation=conversation, position=0, role="user", content="Where is Paris?")
    return messages.create(
        conversation=conversation,
        position=1,
        role="assistant",
        content="In France.",
        thinking=thinking,
        approved=True,
    )


def a_dataset(folder: Path, status: str = Dataset.Status.READY) -> Dataset:
    rows: Path = folder / "rows.jsonl"
    rows.write_text(
        "".join(
            f'{{"messages": [{{"role": "user", "content": "Q{n}"}}, '
            f'{{"role": "assistant", "content": "A{n}"}}]}}\n'
            for n in range(3)
        )
    )
    return DatasetRepository().create(
        name="Questions", source=Dataset.Source.UPLOAD, status=status, rows=3, file_path=str(rows)
    )


def start(client: APIClient, project: Project, **fields: Any) -> ApiResponse:
    body: dict[str, Any] = {"project": str(project.pk), "name": "Polite", **fields}
    return client.post("/api/training/", body, format="json")


def run_now(response: ApiResponse) -> TrainingRun:
    run_id: str = response.json()["id"]
    RunnerService(poll_seconds=0.05).run(run_id)
    run: TrainingRun | None = RunRepository().with_project(run_id)
    assert run is not None
    return run


@pytest.mark.django_db
def test_nothing_to_learn_without_approved_replies(client: APIClient, project: Project) -> None:
    response: ApiResponse = start(client, project)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "nothing_to_learn"


@pytest.mark.django_db
def test_a_run_trains_a_new_version_that_stores_only_the_change(
    client: APIClient, project: Project
) -> None:
    approve_a_reply(project)

    queued: ApiResponse = start(client, project)
    run: TrainingRun = run_now(queued)

    assert queued.status_code == 202
    assert queued.json()["status"] == "queued"
    assert run.status == TrainingRun.Status.COMPLETED, run.error_detail
    assert run.examples == 1
    assert run.version is not None
    version: ModelVersion = run.version
    assert version.kind == ModelVersion.Kind.LORA
    assert version.number == 1
    assert version.name == "Polite"
    assert version.parent is not None and version.parent.kind == ModelVersion.Kind.BASE
    assert (Path(version.storage_dir) / "adapter_model.safetensors").exists()
    assert 0 < version.size_bytes < version.full_size_bytes
    assert version.delta_stats["total_norm"] > 0
    refreshed: Project | None = ProjectRepository().find(str(project.pk))
    assert refreshed is not None and refreshed.active_version_id == version.pk


@pytest.mark.django_db
def test_the_corrections_reach_the_trainer_as_conversations(
    client: APIClient, project: Project
) -> None:
    approve_a_reply(project)

    run: TrainingRun = run_now(start(client, project))

    written: str = (Path(run.run_dir) / "corrections-0.jsonl").read_text()
    assert '"role": "system", "content": "Answer briefly."' in written
    assert '"thinking": "Recall the capital."' in written


@pytest.mark.django_db
def test_a_run_learns_from_a_library_dataset(
    client: APIClient, project: Project, tmp_path: Path
) -> None:
    dataset: Dataset = a_dataset(tmp_path)

    queued: ApiResponse = start(
        client,
        project,
        use_corrections=False,
        datasets=[{"id": str(dataset.pk), "max_rows": 2}],
    )
    run: TrainingRun = run_now(queued)

    assert queued.status_code == 202
    assert queued.json()["datasets"] == [
        {"id": str(dataset.pk), "name": "Questions", "rows": 3, "max_rows": 2}
    ]
    assert run.status == TrainingRun.Status.COMPLETED, run.error_detail
    assert run.examples == 2


@pytest.mark.django_db
def test_a_dataset_still_importing_is_refused(
    client: APIClient, project: Project, tmp_path: Path
) -> None:
    dataset: Dataset = a_dataset(tmp_path, Dataset.Status.IMPORTING)

    response: ApiResponse = start(client, project, datasets=[{"id": str(dataset.pk)}])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "dataset_not_ready"


@pytest.mark.django_db
def test_progress_is_recorded_step_by_step(client: APIClient, project: Project) -> None:
    approve_a_reply(project)
    run: TrainingRun = run_now(start(client, project))

    first: ApiResponse = client.get(f"/api/training/{run.pk}/metrics/")
    later: ApiResponse = client.get(f"/api/training/{run.pk}/metrics/", {"after_step": 1})

    steps: list[int] = [point["step"] for point in first.json()["results"]]
    assert steps == list(range(1, run.total_steps + 1))
    assert all(point["loss"] is not None for point in first.json()["results"])
    assert [point["step"] for point in later.json()["results"]] == steps[1:]


@pytest.mark.django_db
def test_enhancing_a_version_starts_from_its_change(client: APIClient, project: Project) -> None:
    approve_a_reply(project)
    first: TrainingRun = run_now(start(client, project))
    assert first.version is not None

    second: TrainingRun = run_now(start(client, project, starts_from=str(first.version.pk)))

    assert second.version is not None
    assert second.version.parent == first.version
    config: str = (Path(second.run_dir) / "config.json").read_text()
    assert first.version.storage_dir in config


@pytest.mark.django_db
def test_a_failing_trainer_ends_the_run_with_its_reason(
    client: APIClient, project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MESBAH_FAKE_TRAINER", "oom")
    approve_a_reply(project)

    run: TrainingRun = run_now(start(client, project))

    assert run.status == TrainingRun.Status.FAILED
    assert run.error_code == "out_of_memory"
    assert run.version is None


@pytest.mark.django_db
def test_a_running_run_stops_when_cancelled(
    client: APIClient, project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MESBAH_FAKE_TRAINER", "slow")
    approve_a_reply(project)
    queued: ApiResponse = start(client, project)
    pending: TrainingRun | None = RunRepository().find(queued.json()["id"])
    assert pending is not None
    RunRepository().update(pending, cancel_requested=True)

    run: TrainingRun = run_now(queued)

    assert run.status == TrainingRun.Status.CANCELLED
    assert run.version is None


@pytest.mark.django_db
def test_a_waiting_run_is_cancelled_at_once(client: APIClient, project: Project) -> None:
    approve_a_reply(project)
    queued: ApiResponse = start(client, project)

    cancelled: ApiResponse = client.post(f"/api/training/{queued.json()['id']}/cancel/")

    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["cancel_requested"] is True


@pytest.mark.django_db
def test_the_plan_and_the_examples(client: APIClient, project: Project) -> None:
    approve_a_reply(project)

    plan: dict[str, Any] = client.get("/api/training/plan/", {"project": str(project.pk)}).json()
    examples: dict[str, Any] = client.get(
        "/api/training/examples/", {"project": str(project.pk)}
    ).json()

    assert plan["corrections"] == 1
    assert plan["hyperparams"]["lora_rank"] == 16
    assert examples["count"] == 1
    assert [turn["role"] for turn in examples["results"][0]["messages"]] == [
        "system",
        "user",
        "assistant",
    ]


@pytest.mark.django_db
def test_viewers_watch_but_cannot_train(project: Project) -> None:
    approve_a_reply(project)
    users: UserRepository = UserRepository()
    viewer: User = users.add_to_group(users.create(username="noor", password=PASSWORD), VIEWERS)
    api: APIClient = APIClient()
    api.force_login(viewer)

    assert api.get("/api/training/", {"project": str(project.pk)}).status_code == 200
    assert start(api, project).status_code == 403


@pytest.mark.django_db
def test_the_engine_waits_while_a_run_trains(trainer: User, project: Project) -> None:
    approve_a_reply(project)
    queued: TrainingRun = TrainingService(trainer).create(project=str(project.pk))
    RunRepository().update(queued, status=TrainingRun.Status.TRAINING)
    root: ModelVersion | None = project.active_version
    assert root is not None

    def empty_engine(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"loaded": False})

    EngineClient.transport = httpx2.MockTransport(empty_engine)
    with pytest.raises(EngineFailed) as refused:
        DeploymentService(trainer).target(root)

    assert refused.value.default_code == "training_in_progress"
