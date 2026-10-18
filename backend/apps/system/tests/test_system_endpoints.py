from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx2
import pytest
from django.conf import LazySettings
from django.contrib.auth.models import User
from huggingface_hub import HfApi
from huggingface_hub.errors import HfHubHTTPError
from rest_framework.test import APIClient

from apps.accounts.repositories import UserRepository
from apps.members.roles import ADMINS
from apps.system.models import Secret
from apps.system.repositories import SecretRepository
from apps.system.services import SecretBox
from apps.system.services.system_service import HUGGINGFACE_TOKEN
from mesbah import hardware

if TYPE_CHECKING:
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

PASSWORD: str = "correct-horse-battery-staple"  # noqa: S105
TOKEN: str = "hf_abcdefghijklmnopqrstuvwxyz1234"  # noqa: S105
GIB: int = 1024**3

TWO_GPUS: tuple[hardware.Gpu, ...] = (
    hardware.Gpu(index=0, name="RTX 5080", memory_bytes=16 * GIB, compute_capability="12.0"),
    hardware.Gpu(index=1, name="RTX 3060", memory_bytes=12 * GIB, compute_capability="8.6"),
)


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def admin(db: None) -> User:
    users: UserRepository = UserRepository()
    return users.add_to_group(users.create(username="admin", password=PASSWORD), ADMINS)


@pytest.fixture
def member(db: None) -> User:
    return UserRepository().create(username="sara", password=PASSWORD)


@pytest.fixture
def two_gpus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hardware, "gpus", lambda: (TWO_GPUS, "595.71.05"))


@pytest.fixture
def no_gpus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hardware, "gpus", lambda: ((), None))


@pytest.fixture
def data_dir(settings: LazySettings, tmp_path: Path) -> None:
    settings.MESBAH_DATA_DIR = tmp_path / "data"


def accepted_by_huggingface(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(HfApi, "whoami", lambda _self, token=None, **_kw: {"name": "sara-hf"})


def refused_by_huggingface(monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    def refuse(_self: HfApi, token: str | None = None, **_kw: object) -> dict[str, Any]:
        response: httpx2.Response = httpx2.Response(
            status, request=httpx2.Request("GET", "https://huggingface.co/api/whoami-v2")
        )
        raise HfHubHTTPError("refused", response=response)

    monkeypatch.setattr(HfApi, "whoami", refuse)


@pytest.mark.django_db
@pytest.mark.usefixtures("no_gpus", "data_dir")
def test_overview_without_a_gpu(client: APIClient, member: User) -> None:
    client.force_login(member)

    response: ApiResponse = client.get("/api/system/")

    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    assert body["machine"]["gpus"] == []
    assert body["selected_gpus"] == []
    assert body["usable_vram_bytes"] == 0
    assert body["storage"]["free_bytes"] > 0
    assert {part["name"] for part in body["parts"]} >= {"torch", "transformers", "peft"}
    assert body["huggingface"] == {"configured": False, "hint": "", "account": ""}


@pytest.mark.django_db
@pytest.mark.usefixtures("two_gpus", "data_dir")
def test_the_largest_gpu_is_chosen_until_someone_picks(client: APIClient, member: User) -> None:
    client.force_login(member)

    body: dict[str, Any] = client.get("/api/system/").json()

    assert body["gpu_choice"] == "automatic"
    assert body["selected_gpus"] == [0]
    assert body["usable_vram_bytes"] == 16 * GIB


@pytest.mark.django_db
@pytest.mark.usefixtures("two_gpus", "data_dir")
def test_an_administrator_picks_both_gpus(client: APIClient, admin: User) -> None:
    client.force_login(admin)

    response: ApiResponse = client.put("/api/system/gpus/", {"gpus": [1, 0]}, format="json")

    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    assert body["gpu_choice"] == "chosen"
    assert body["selected_gpus"] == [0, 1]
    assert body["usable_vram_bytes"] == 28 * GIB


@pytest.mark.django_db
@pytest.mark.usefixtures("two_gpus", "data_dir")
def test_an_empty_choice_goes_back_to_automatic(client: APIClient, admin: User) -> None:
    client.force_login(admin)
    client.put("/api/system/gpus/", {"gpus": [1]}, format="json")

    body: dict[str, Any] = client.put("/api/system/gpus/", {"gpus": []}, format="json").json()

    assert body["gpu_choice"] == "automatic"
    assert body["selected_gpus"] == [0]


@pytest.mark.django_db
@pytest.mark.usefixtures("two_gpus", "data_dir")
def test_a_gpu_that_is_not_there_is_refused(client: APIClient, admin: User) -> None:
    client.force_login(admin)

    response: ApiResponse = client.put("/api/system/gpus/", {"gpus": [7]}, format="json")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unknown_gpu"


@pytest.mark.django_db
@pytest.mark.usefixtures("two_gpus", "data_dir")
def test_only_an_administrator_changes_the_system(client: APIClient, member: User) -> None:
    client.force_login(member)

    assert client.put("/api/system/gpus/", {"gpus": [0]}, format="json").status_code == 403
    assert (
        client.put("/api/system/huggingface-token/", {"token": TOKEN}, format="json").status_code
        == 403
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("no_gpus", "data_dir")
def test_a_saved_token_is_never_sent_back(
    client: APIClient, admin: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    accepted_by_huggingface(monkeypatch)
    client.force_login(admin)

    response: ApiResponse = client.put(
        "/api/system/huggingface-token/", {"token": TOKEN}, format="json"
    )

    assert response.status_code == 200
    assert TOKEN not in response.content.decode()
    assert response.json()["huggingface"] == {
        "configured": True,
        "hint": "1234",
        "account": "sara-hf",
    }
    stored: Secret | None = SecretRepository().find_by_name(HUGGINGFACE_TOKEN)
    assert stored is not None
    assert TOKEN not in stored.ciphertext
    assert SecretBox().open(stored.ciphertext) == TOKEN


@pytest.mark.django_db
@pytest.mark.usefixtures("no_gpus", "data_dir")
def test_a_token_huggingface_refuses_is_not_saved(
    client: APIClient, admin: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    refused_by_huggingface(monkeypatch, 401)
    client.force_login(admin)

    response: ApiResponse = client.put(
        "/api/system/huggingface-token/", {"token": TOKEN}, format="json"
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "hf_token_rejected"
    assert SecretRepository().find_by_name(HUGGINGFACE_TOKEN) is None


@pytest.mark.django_db
@pytest.mark.usefixtures("no_gpus", "data_dir")
def test_huggingface_being_down_is_its_own_error(
    client: APIClient, admin: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    refused_by_huggingface(monkeypatch, 502)
    client.force_login(admin)

    response: ApiResponse = client.put(
        "/api/system/huggingface-token/", {"token": TOKEN}, format="json"
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "hf_unreachable"


@pytest.mark.django_db
@pytest.mark.usefixtures("no_gpus", "data_dir")
def test_removing_the_token(
    client: APIClient, admin: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    accepted_by_huggingface(monkeypatch)
    client.force_login(admin)
    client.put("/api/system/huggingface-token/", {"token": TOKEN}, format="json")

    response: ApiResponse = client.delete("/api/system/huggingface-token/")

    assert response.status_code == 200
    assert response.json()["huggingface"]["configured"] is False


def test_a_secret_sealed_under_another_key_does_not_open() -> None:
    sealed: str = SecretBox("first-key").seal(TOKEN)

    assert SecretBox("first-key").open(sealed) == TOKEN
    assert SecretBox("second-key").open(sealed) is None
