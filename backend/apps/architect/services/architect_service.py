from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any

from django.contrib.auth.models import AnonymousUser, User
from django.db import transaction
from django.db.models import QuerySet
from rest_framework.exceptions import NotFound

from apps.architect.models import ArchitectureDraft
from apps.architect.repositories import DraftRepository
from apps.architect.services.errors import DesignRefused, TokenizerNeeded
from apps.models.models import HubModel
from apps.models.repositories import HubModelRepository
from apps.projects.models import Project
from apps.projects.services import ProjectService
from apps.system.services import SystemService
from apps.training.models import TrainingRun
from apps.training.services import TrainingService
from mesbah import architect


def design_of(data: dict[str, Any]) -> architect.Design:
    try:
        return architect.Design.from_json(data)
    except architect.DesignError as error:
        raise DesignRefused(error.code, error.field) from error


class ArchitectService:
    def __init__(self, user: User | AnonymousUser) -> None:
        self.user: User | AnonymousUser = user
        self.drafts: DraftRepository = DraftRepository()
        self.models: HubModelRepository = HubModelRepository()
        self.system: SystemService = SystemService(user)

    def presets(self) -> list[dict[str, Any]]:
        return [
            {
                "name": preset.name,
                "design": preset.design.to_json(),
                "counts": asdict(preset.counts),
            }
            for preset in architect.presets()
        ]

    def estimate(
        self, design: dict[str, Any], seq_len: int, batch: int, tokenizer: str = ""
    ) -> dict[str, Any]:
        designed: architect.Design = design_of(design)
        vocabulary: int | None = self.tokenizer_vocabulary(tokenizer)
        built: architect.Design = (
            replace(designed, vocab_size=vocabulary)
            if vocabulary is not None and vocabulary > designed.vocab_size
            else designed
        )
        memory: architect.Memory = architect.memory(
            built, self.system.usable_vram_bytes(), seq_len, batch
        )
        return {
            "design": designed.to_json(),
            "counts": asdict(architect.count(built)),
            "memory": asdict(memory),
            "note": architect.vocabulary_note(built),
            "tokenizer_vocabulary": vocabulary,
        }

    def tokenizer_vocabulary(self, tokenizer: str) -> int | None:
        model: HubModel | None = self.models.find_by_repo(tokenizer) if tokenizer else None
        size: object = None if model is None else model.architecture.get("vocab_size")
        return size if isinstance(size, int) and size > 0 else None

    def listing(self) -> QuerySet[ArchitectureDraft]:
        return self.drafts.listing()

    def find(self, draft_id: str) -> ArchitectureDraft:
        draft: ArchitectureDraft | None = self.drafts.find(draft_id)
        if draft is None:
            raise NotFound
        return draft

    def describe(self, draft: ArchitectureDraft) -> dict[str, Any]:
        return {
            "id": draft.pk,
            "name": draft.name,
            "notes": draft.notes,
            "tokenizer": draft.tokenizer,
            "seq_len": draft.seq_len,
            "batch": draft.batch,
            **self.estimate(draft.design, draft.seq_len, draft.batch, draft.tokenizer),
            "created_at": draft.created_at,
            "updated_at": draft.updated_at,
            "created_by": None if draft.created_by is None else draft.created_by.get_username(),
        }

    def create(self, *, design: dict[str, Any], **fields: Any) -> ArchitectureDraft:
        return self.drafts.create(
            created_by=self.user if isinstance(self.user, User) else None,
            design=design_of(design).to_json(),
            **fields,
        )

    def change(self, draft_id: str, **fields: Any) -> ArchitectureDraft:
        draft: ArchitectureDraft = self.find(draft_id)
        if "design" in fields:
            fields["design"] = design_of(fields["design"]).to_json()
        return self.drafts.update(draft, **fields) if fields else draft

    @transaction.atomic
    def train(
        self,
        draft_id: str,
        *,
        name: str,
        corrections_from: list[str],
        datasets: list[dict[str, Any]] | None = None,
        hyperparams: dict[str, Any] | None = None,
    ) -> TrainingRun:
        draft: ArchitectureDraft = self.find(draft_id)
        if not draft.tokenizer:
            raise TokenizerNeeded
        project: Project = ProjectService(self.user).create_scratch(
            name=name, description=draft.notes
        )
        return TrainingService(self.user).create_pretrain(
            project=project,
            draft=draft,
            corrections_from=corrections_from,
            datasets=datasets or [],
            hyperparams=hyperparams,
        )

    def remove(self, draft_id: str) -> None:
        self.drafts.soft_delete(self.find(draft_id))
