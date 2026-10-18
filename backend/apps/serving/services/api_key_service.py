from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any

from django.contrib.auth.models import AnonymousUser, User
from django.db.models import QuerySet
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.members.roles import ADMINS
from apps.serving.models import ApiKey
from apps.serving.repositories import ApiKeyRepository

KEY_PREFIX: str = "msb_"
SHOWN: int = 8
TOUCH_EVERY: timedelta = timedelta(minutes=1)


def digest_of(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


class ApiKeyService:
    def __init__(self, user: User | AnonymousUser) -> None:
        self.user: User | AnonymousUser = user
        self.keys: ApiKeyRepository = ApiKeyRepository()

    def listing(self) -> QuerySet[ApiKey]:
        if self._sees_all():
            return self.keys.listing()
        return self.keys.owned_by(self._owner())

    def describe(self, key: ApiKey) -> dict[str, Any]:
        return {
            "id": key.pk,
            "name": key.name,
            "prefix": key.prefix,
            "owner": None if key.created_by is None else key.created_by.get_username(),
            "last_used_at": key.last_used_at,
            "created_at": key.created_at,
        }

    def create(self, name: str) -> dict[str, Any]:
        secret: str = KEY_PREFIX + secrets.token_urlsafe(32)
        key: ApiKey = self.keys.create(
            created_by=self._owner(),
            name=name,
            prefix=secret[: len(KEY_PREFIX) + SHOWN],
            digest=digest_of(secret),
        )
        return {**self.describe(key), "key": secret}

    def revoke(self, key_id: str) -> None:
        key: ApiKey | None = self.listing().filter(pk=key_id).first()
        if key is None:
            raise NotFound
        self.keys.soft_delete(key)

    def authenticate(self, secret: str) -> ApiKey | None:
        key: ApiKey | None = self.keys.by_digest(digest_of(secret))
        if key is None or key.created_by is None or not key.created_by.is_active:
            return None
        now: datetime = timezone.now()
        if key.last_used_at is None or now - key.last_used_at > TOUCH_EVERY:
            key = self.keys.update(key, last_used_at=now)
        return key

    def _sees_all(self) -> bool:
        user: User | AnonymousUser = self.user
        return isinstance(user, User) and (
            user.is_superuser or user.groups.filter(name=ADMINS).exists()
        )

    def _owner(self) -> User:
        if not isinstance(self.user, User):
            raise NotFound
        return self.user
