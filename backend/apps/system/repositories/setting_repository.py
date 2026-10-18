from __future__ import annotations

from django.contrib.auth.base_user import AbstractBaseUser

from apps.common.repositories import BaseRepository
from apps.system.models import Setting


class SettingRepository(BaseRepository[Setting]):
    model = Setting

    def find_by_key(self, key: str) -> Setting | None:
        return self.active().filter(key=key).first()

    def put(self, key: str, value: object, *, by: AbstractBaseUser | None) -> Setting:
        existing: Setting | None = self.find_by_key(key)
        if existing is None:
            return self.create(created_by=by, key=key, value=value)
        return self.update(existing, value=value)
