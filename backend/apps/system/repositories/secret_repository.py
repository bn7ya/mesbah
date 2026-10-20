from __future__ import annotations

from django.contrib.auth.base_user import AbstractBaseUser

from apps.common.repositories import BaseRepository
from apps.system.models import Secret


class SecretRepository(BaseRepository[Secret]):
    model = Secret

    def find_by_name(self, name: str) -> Secret | None:
        return self.active().filter(name=name).first()

    def put(
        self, name: str, *, ciphertext: str, hint: str, account: str, by: AbstractBaseUser | None
    ) -> Secret:
        existing: Secret | None = self.find_by_name(name)
        if existing is None:
            return self.create(
                created_by=by, name=name, ciphertext=ciphertext, hint=hint, account=account
            )
        return self.update(existing, ciphertext=ciphertext, hint=hint, account=account)
