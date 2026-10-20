from __future__ import annotations

import sys
from pathlib import Path

import pytest
from django.conf import LazySettings

from apps.models.models import HubModel
from apps.models.repositories import HubModelRepository
from apps.models.services import download_service
from apps.models.services.download_service import DownloadService

SUCCEEDS: str = (
    "import json, pathlib, sys; "
    "target = pathlib.Path(sys.argv[1]) / 'models--org--tiny' / 'snapshots' / 'abc'; "
    "target.mkdir(parents=True); (target / 'model.safetensors').write_bytes(b'0' * 64); "
    "print(json.dumps({'path': str(target)}))"
)
FAILS: str = (
    "import json; print(json.dumps({'error': 'gated', 'detail': 'no access'})); raise SystemExit(1)"
)


@pytest.fixture(autouse=True)
def data_dir(settings: LazySettings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings.MESBAH_DATA_DIR = tmp_path
    monkeypatch.setattr(download_service, "POLL_SECONDS", 0.05)


def queued() -> HubModel:
    return HubModelRepository().create(
        repo_id="org/tiny", status=HubModel.Status.QUEUED, size_bytes=64
    )


def scripted(monkeypatch: pytest.MonkeyPatch, script: str) -> None:
    def command(_self: DownloadService, _row: HubModel, cache_dir: Path) -> list[str]:
        return [sys.executable, "-c", script, str(cache_dir)]

    monkeypatch.setattr(DownloadService, "command", command)


@pytest.mark.django_db
def test_a_finished_download_is_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    scripted(monkeypatch, SUCCEEDS)
    row: HubModel = queued()

    DownloadService().run(str(row.pk))

    done: HubModel | None = HubModelRepository().find(row.pk)
    assert done is not None
    assert done.status == HubModel.Status.READY
    assert done.local_path.endswith("snapshots/abc")
    assert done.downloaded_bytes == 64
    assert done.downloaded_at is not None


@pytest.mark.django_db
def test_a_gated_model_fails_with_its_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    scripted(monkeypatch, FAILS)
    row: HubModel = queued()

    DownloadService().run(str(row.pk))

    failed: HubModel | None = HubModelRepository().find(row.pk)
    assert failed is not None
    assert (failed.status, failed.error_code) == (HubModel.Status.FAILED, "gated")


@pytest.mark.django_db
def test_a_cancelled_download_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    scripted(monkeypatch, "import time; time.sleep(30)")
    row: HubModel = queued()
    monkeypatch.setattr(HubModelRepository, "cancel_requested", lambda _self, _id: True)

    DownloadService().run(str(row.pk))

    stopped: HubModel | None = HubModelRepository().find(row.pk)
    assert stopped is not None
    assert stopped.status == HubModel.Status.CANCELLED
    assert stopped.cancel_requested is False
