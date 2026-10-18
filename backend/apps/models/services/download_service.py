from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from apps.models.models import HubModel
from apps.models.repositories import HubModelRepository
from apps.models.services.storage import directory_size, hub_cache_dir
from apps.system.services import SystemService
from mesbah.download import repo_cache_dir

POLL_SECONDS: float = 2.0
STOP_SECONDS: float = 10.0


class DownloadService:
    def __init__(self) -> None:
        self.models: HubModelRepository = HubModelRepository()

    def command(self, row: HubModel, cache_dir: Path) -> list[str]:
        command: list[str] = [
            sys.executable,
            "-m",
            "mesbah.download",
            row.repo_id,
            "--cache-dir",
            str(cache_dir),
        ]
        if row.revision:
            command += ["--revision", row.revision]
        for name in row.files:
            command += ["--file", str(name)]
        return command

    def run(self, model_id: str) -> None:
        row: HubModel | None = self.models.find(model_id)
        if row is None or row.status != HubModel.Status.QUEUED:
            return
        if row.cancel_requested:
            self.models.update(row, status=HubModel.Status.CANCELLED, cancel_requested=False)
            return
        row = self.models.update(row, status=HubModel.Status.DOWNLOADING, error_code="")
        cache_dir: Path = hub_cache_dir()
        target: Path = repo_cache_dir(cache_dir, row.repo_id)
        environment: dict[str, str] = {**os.environ, "HF_HUB_DISABLE_PROGRESS_BARS": "1"}
        token: str | None = SystemService(AnonymousUser()).huggingface_token()
        if token:
            environment["HF_TOKEN"] = token
        process: subprocess.Popen[str] = subprocess.Popen(  # noqa: S603
            self.command(row, cache_dir),
            env=environment,
            cwd=settings.BASE_DIR,
            stdout=subprocess.PIPE,
            text=True,
        )
        while process.poll() is None:
            self.models.set_progress(model_id, directory_size(target))
            if self.models.cancel_requested(model_id):
                process.terminate()
                process.wait(timeout=STOP_SECONDS)
                self._finish(model_id, HubModel.Status.CANCELLED)
                return
            time.sleep(POLL_SECONDS)
        output: str = process.stdout.read() if process.stdout else ""
        self._settle(model_id, process.returncode, output)

    def _settle(self, model_id: str, code: int, output: str) -> None:
        reply: dict[str, str] = {}
        for line in reversed(output.strip().splitlines()):
            try:
                parsed: object = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                reply = {str(key): str(value) for key, value in parsed.items()}
                break
        if code == 0 and "path" in reply:
            row: HubModel | None = self.models.find(model_id)
            if row is not None:
                self.models.update(
                    row,
                    status=HubModel.Status.READY,
                    local_path=reply["path"],
                    downloaded_bytes=row.size_bytes,
                    downloaded_at=timezone.now(),
                    cancel_requested=False,
                )
            return
        self._finish(model_id, HubModel.Status.FAILED, reply.get("error", "network"))

    def _finish(self, model_id: str, status: str, error_code: str = "") -> None:
        row: HubModel | None = self.models.find(model_id)
        if row is not None:
            self.models.update(row, status=status, error_code=error_code, cancel_requested=False)
