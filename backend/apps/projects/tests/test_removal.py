from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.accounts.repositories import UserRepository
from apps.chat.models import Conversation, Message
from apps.chat.repositories import ConversationRepository, MessageRepository
from apps.members.roles import TRAINERS, VIEWERS
from apps.models.models import HubModel
from apps.models.repositories import HubModelRepository
from apps.projects.models import Project
from apps.projects.repositories import ProjectRepository
from apps.training.models import TrainingMetric, TrainingRun
from apps.training.repositories import MetricRepository, RunRepository
from apps.versions.models import Export, ModelVersion
from apps.versions.repositories import ExportRepository, VersionRepository

if TYPE_CHECKING:
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

PASSWORD: str = "correct-horse-battery-staple"  # noqa: S105


def member(role: str) -> APIClient:
    users: UserRepository = UserRepository()
    user: User = users.add_to_group(users.create(username=role, password=PASSWORD), role)
    api: APIClient = APIClient()
    api.force_login(user)
    return api


@pytest.mark.django_db
def test_removing_a_project_removes_everything_under_it() -> None:
    model: HubModel = HubModelRepository().create(
        repo_id="org/tiny", status=HubModel.Status.READY, local_path="/models/org-tiny"
    )
    project: Project = ProjectRepository().create(name="Tiny", slug="tiny", base_model=model)
    root: ModelVersion = VersionRepository().create(
        project=project, number=0, kind=ModelVersion.Kind.BASE, name="base"
    )
    version: ModelVersion = VersionRepository().create(
        project=project, parent=root, number=1, kind=ModelVersion.Kind.LORA
    )
    export: Export = ExportRepository().create(version=version, format=Export.Format.LORA)
    conversation: Conversation = ConversationRepository().create(project=project, title="Hi")
    message: Message = MessageRepository().create(
        conversation=conversation, position=0, role="user", content="Hello"
    )
    run: TrainingRun = RunRepository().create(
        project=project, parent=root, status=TrainingRun.Status.TRAINING
    )
    MetricRepository().record([TrainingMetric(run=run, step=1, loss=2.0)])
    trainer: APIClient = member(TRAINERS)
    viewer: APIClient = member(VIEWERS)

    removed: ApiResponse = trainer.delete(f"/api/projects/{project.pk}/")

    assert removed.status_code == 204
    for path in (
        f"/api/chat/{conversation.pk}/",
        f"/api/chat/{conversation.pk}/messages/",
        f"/api/chat/messages/{message.pk}/",
        f"/api/versions/{version.pk}/",
        f"/api/versions/{version.pk}/exports/",
        f"/api/versions/exports/{export.pk}/",
        f"/api/training/{run.pk}/",
        f"/api/training/{run.pk}/metrics/",
    ):
        assert viewer.get(path).status_code == 404, path
    renamed: ApiResponse = trainer.patch(
        f"/api/chat/{conversation.pk}/", {"title": "Still here?"}, format="json"
    )
    assert renamed.status_code == 404
    assert RunRepository().cancel_requested(str(run.pk))
    assert not RunRepository().unfinished().filter(pk=run.pk).exists()
