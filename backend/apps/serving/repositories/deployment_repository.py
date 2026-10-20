from __future__ import annotations

from django.db.models import QuerySet

from apps.common.repositories import BaseRepository
from apps.serving.models import Deployment, Engine
from apps.versions.models import ModelVersion


class DeploymentRepository(BaseRepository[Deployment]):
    model = Deployment

    def on_engine(self, engine: Engine) -> QuerySet[Deployment]:
        return (
            self.active()
            .filter(engine=engine)
            .exclude(status=Deployment.Status.UNLOADED)
            .select_related("version", "version__project")
        )

    def of(self, engine: Engine, version: ModelVersion) -> Deployment | None:
        return self.active().filter(engine=engine, version=version).first()

    def mark_unloaded(self, engine: Engine) -> int:
        return (
            self.active()
            .filter(engine=engine)
            .exclude(status=Deployment.Status.UNLOADED)
            .update(status=Deployment.Status.UNLOADED)
        )
