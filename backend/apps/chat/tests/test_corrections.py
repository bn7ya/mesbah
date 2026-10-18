from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.accounts.repositories import UserRepository
from apps.chat.models import Conversation, Message
from apps.chat.repositories import ConversationRepository, MessageRepository
from apps.members.roles import REVIEWERS, VIEWERS
from apps.models.models import HubModel
from apps.models.repositories import HubModelRepository
from apps.projects.models import Project
from apps.projects.repositories import ProjectRepository

if TYPE_CHECKING:
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

PASSWORD: str = "correct-horse-battery-staple"  # noqa: S105


@pytest.fixture
def reviewer(db: None) -> User:
    users: UserRepository = UserRepository()
    return users.add_to_group(users.create(username="rana", password=PASSWORD), REVIEWERS)


@pytest.fixture
def client(reviewer: User) -> APIClient:
    api: APIClient = APIClient()
    api.force_login(reviewer)
    return api


def reply(content: str = "Paris is in Germany.", thinking: str = "") -> Message:
    model: HubModel = HubModelRepository().create(repo_id="org/tiny", status="ready")
    project: Project = ProjectRepository().create(name="Tiny", slug="tiny", base_model=model)
    conversation: Conversation = ConversationRepository().create(project=project)
    messages: MessageRepository = MessageRepository()
    messages.create(conversation=conversation, position=0, role="user", content="Where is Paris?")
    return messages.create(
        conversation=conversation,
        position=1,
        role="assistant",
        content=content,
        thinking=thinking,
    )


def edit(client: APIClient, message: dict[str, Any], **fields: Any) -> ApiResponse:
    body: dict[str, Any] = {"seen": message["updated_at"], **fields}
    return client.patch(f"/api/chat/messages/{message['id']}/", body, format="json")


def opened(client: APIClient, message: Message) -> dict[str, Any]:
    body: dict[str, Any] = client.get(f"/api/chat/messages/{message.pk}/").json()
    return body


@pytest.mark.django_db
def test_correcting_a_reply_keeps_what_the_model_wrote(client: APIClient) -> None:
    message: Message = reply()

    response: ApiResponse = edit(client, opened(client, message), content="Paris is in France.")

    body: dict[str, Any] = response.json()
    assert body["content"] == "Paris is in France."
    assert body["original_content"] == "Paris is in Germany."
    assert body["content_edited_at"] is not None
    assert body["thinking_edited_at"] is None
    assert body["approved"] is True
    assert body["approved_by"] == body["edited_by"] == "rana"


@pytest.mark.django_db
def test_the_thinking_chain_is_corrected_on_its_own(client: APIClient) -> None:
    message: Message = reply(thinking="Paris sounds German.")

    body: dict[str, Any] = edit(
        client, opened(client, message), thinking="Paris is the capital of France."
    ).json()

    assert body["thinking"] == "Paris is the capital of France."
    assert body["original_thinking"] == "Paris sounds German."
    assert body["content"] == "Paris is in Germany."
    assert body["original_content"] is None


@pytest.mark.django_db
def test_a_reply_can_gain_a_thinking_chain_it_never_had(client: APIClient) -> None:
    message: Message = reply()

    body: dict[str, Any] = edit(
        client, opened(client, message), thinking="Recall the capital."
    ).json()

    assert body["thinking"] == "Recall the capital."
    assert body["original_thinking"] == ""


@pytest.mark.django_db
def test_a_second_correction_keeps_the_first_original(client: APIClient) -> None:
    message: Message = reply()
    first: dict[str, Any] = edit(client, opened(client, message), content="Paris: France.").json()

    second: dict[str, Any] = edit(client, first, content="Paris is in France.").json()

    assert second["original_content"] == "Paris is in Germany."


@pytest.mark.django_db
def test_an_edit_from_a_stale_copy_is_refused(client: APIClient) -> None:
    message: Message = reply()
    stale: dict[str, Any] = opened(client, message)
    edit(client, stale, content="Paris is in France.")

    response: ApiResponse = edit(client, stale, content="Paris is in Spain.")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "message_changed"


@pytest.mark.django_db
def test_restoring_puts_back_the_original(client: APIClient) -> None:
    message: Message = reply()
    edited: dict[str, Any] = edit(client, opened(client, message), content="Paris: France.").json()

    response: ApiResponse = client.post(
        f"/api/chat/messages/{message.pk}/restore/",
        {"seen": edited["updated_at"], "part": "content"},
        format="json",
    )

    body: dict[str, Any] = response.json()
    assert body["content"] == "Paris is in Germany."
    assert body["original_content"] is None
    assert body["content_edited_at"] is None


@pytest.mark.django_db
def test_approving_a_reply_as_it_is(client: APIClient) -> None:
    message: Message = reply(content="Paris is in France.")

    approved: ApiResponse = client.post(
        f"/api/chat/messages/{message.pk}/approve/", {"approved": True}, format="json"
    )
    withdrawn: ApiResponse = client.post(
        f"/api/chat/messages/{message.pk}/approve/", {"approved": False}, format="json"
    )

    assert approved.json()["approved"] is True
    assert withdrawn.json()["approved"] is False
    assert withdrawn.json()["approved_by"] is None


@pytest.mark.django_db
def test_the_question_is_not_a_reply_to_correct(client: APIClient) -> None:
    message: Message = reply()
    question: Message | None = (
        MessageRepository().of_conversation(str(message.conversation_id)).first()
    )
    assert question is not None

    response: ApiResponse = edit(client, opened(client, question), content="Where is Rome?")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_editable"


@pytest.mark.django_db
def test_viewers_cannot_correct(client: APIClient) -> None:
    message: Message = reply()
    users: UserRepository = UserRepository()
    viewer: User = users.add_to_group(users.create(username="noor", password=PASSWORD), VIEWERS)
    api: APIClient = APIClient()
    api.force_login(viewer)

    assert edit(api, opened(api, message), content="x").status_code == 403
