from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx2
from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from huggingface_hub import HfApi
from huggingface_hub.errors import HfHubHTTPError

from apps.system.models import Secret, Setting
from apps.system.repositories import SecretRepository, SettingRepository
from apps.system.services.errors import HuggingFaceTokenRejected, HuggingFaceUnreachable, UnknownGpu
from apps.system.services.secret_box import SecretBox
from mesbah import hardware, parts
from mesbah.paths import ensure

SELECTED_GPUS: str = "selected_gpus"
HUGGINGFACE_TOKEN: str = "huggingface_token"  # noqa: S105 - the secret's name, not its value
HINT_LENGTH: int = 4


class SystemService:
    def __init__(self, user: User | AnonymousUser) -> None:
        self.user: User | AnonymousUser = user
        self.settings: SettingRepository = SettingRepository()
        self.secrets: SecretRepository = SecretRepository()
        self.box: SecretBox = SecretBox()

    def overview(self) -> dict[str, Any]:
        machine: hardware.Machine = hardware.machine()
        chosen: list[int] = self._chosen_indices(machine.gpus)
        selected: tuple[hardware.Gpu, ...] = self._effective(machine.gpus, chosen)
        return {
            "machine": {
                "gpus": [vars(gpu) for gpu in machine.gpus],
                "driver": machine.driver,
                "ram_bytes": machine.ram_bytes,
                "cpu_count": machine.cpu_count,
                "system": machine.system,
                "python": machine.python,
            },
            "selected_gpus": [gpu.index for gpu in selected],
            "gpu_choice": "chosen" if chosen else "automatic",
            "usable_vram_bytes": sum(gpu.memory_bytes for gpu in selected),
            "storage": self._storage(settings.MESBAH_DATA_DIR),
            "parts": self._parts(),
            "huggingface": self._huggingface(),
        }

    def usable_vram_bytes(self) -> int:
        machine: hardware.Machine = hardware.machine()
        chosen: list[int] = self._chosen_indices(machine.gpus)
        return sum(gpu.memory_bytes for gpu in self._effective(machine.gpus, chosen))

    def selected_gpu_indices(self) -> list[int]:
        machine: hardware.Machine = hardware.machine()
        chosen: list[int] = self._chosen_indices(machine.gpus)
        return [gpu.index for gpu in self._effective(machine.gpus, chosen)]

    def huggingface_token(self) -> str | None:
        secret: Secret | None = self.secrets.find_by_name(HUGGINGFACE_TOKEN)
        return None if secret is None else self.box.open(secret.ciphertext)

    def select_gpus(self, indices: list[int]) -> dict[str, Any]:
        known: set[int] = {gpu.index for gpu in hardware.machine().gpus}
        if any(index not in known for index in indices):
            raise UnknownGpu
        self.settings.put(SELECTED_GPUS, sorted(set(indices)), by=self._actor())
        return self.overview()

    def save_huggingface_token(self, token: str) -> dict[str, Any]:
        account: str = self._account_for(token)
        self.secrets.put(
            HUGGINGFACE_TOKEN,
            ciphertext=self.box.seal(token),
            hint=token[-HINT_LENGTH:],
            account=account,
            by=self._actor(),
        )
        return self.overview()

    def remove_huggingface_token(self) -> dict[str, Any]:
        existing: Secret | None = self.secrets.find_by_name(HUGGINGFACE_TOKEN)
        if existing is not None:
            self.secrets.soft_delete(existing)
        return self.overview()

    def _actor(self) -> User | None:
        return self.user if isinstance(self.user, User) else None

    def _chosen_indices(self, gpus: tuple[hardware.Gpu, ...]) -> list[int]:
        stored: Setting | None = self.settings.find_by_key(SELECTED_GPUS)
        if stored is None or not isinstance(stored.value, list):
            return []
        known: set[int] = {gpu.index for gpu in gpus}
        return [index for index in stored.value if isinstance(index, int) and index in known]

    @staticmethod
    def _effective(gpus: tuple[hardware.Gpu, ...], chosen: list[int]) -> tuple[hardware.Gpu, ...]:
        if chosen:
            return tuple(gpu for gpu in gpus if gpu.index in chosen)
        if not gpus:
            return ()
        return (max(gpus, key=lambda gpu: gpu.memory_bytes),)

    @staticmethod
    def _storage(path: Path) -> dict[str, Any]:
        usage: shutil._ntuple_diskusage = shutil.disk_usage(ensure(path))
        return {"path": str(path), "free_bytes": usage.free, "total_bytes": usage.total}

    def _parts(self) -> list[dict[str, Any]]:
        here: tuple[parts.Part, ...] = parts.parts()
        engine: dict[str, str] = (
            self._engine_parts() if any(part.version is None for part in here) else {}
        )
        shown: list[dict[str, Any]] = []
        for part in here:
            from_engine: bool = part.version is None and part.name in engine
            seen: parts.Part = replace(part, version=engine[part.name]) if from_engine else part
            found_in: str | None = (
                "engine" if from_engine else None if part.version is None else "web"
            )
            shown.append(
                {
                    "name": seen.name,
                    "purpose": seen.purpose,
                    "version": seen.version,
                    "cuda": seen.cuda,
                    "found_in": found_in,
                }
            )
        return shown

    @staticmethod
    def _engine_parts() -> dict[str, str]:
        # apps.serving imports this module, so it is imported where it is used.
        from apps.serving.services.deployment_service import builtin_endpoint
        from apps.serving.services.engine_client import EngineClient, EngineError

        try:
            status: dict[str, object] = EngineClient(builtin_endpoint()).status()
        except EngineError:
            return {}
        reported: object = status.get("parts")
        if not isinstance(reported, list):
            return {}
        return {
            row["name"]: row["version"]
            for row in reported
            if isinstance(row, dict)
            and isinstance(row.get("name"), str)
            and isinstance(row.get("version"), str)
        }

    def _huggingface(self) -> dict[str, Any]:
        secret: Secret | None = self.secrets.find_by_name(HUGGINGFACE_TOKEN)
        if secret is None or self.box.open(secret.ciphertext) is None:
            return {"configured": False, "hint": "", "account": ""}
        return {"configured": True, "hint": secret.hint, "account": secret.account}

    @staticmethod
    def _account_for(token: str) -> str:
        try:
            identity: dict[str, Any] = HfApi().whoami(token=token)
        except HfHubHTTPError as error:
            if error.response.status_code in {401, 403}:
                raise HuggingFaceTokenRejected from error
            raise HuggingFaceUnreachable from error
        except (httpx2.HTTPError, OSError) as error:
            raise HuggingFaceUnreachable from error
        return str(identity.get("name", ""))
