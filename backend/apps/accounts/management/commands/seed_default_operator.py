"""Seed the one local operator account Mesbah needs.

Mesbah is a local, single-user studio — adopting Django auth (rule 20) does
not make it a multi-tenant product. Rather than a signup flow, first boot
gets exactly one superuser account so the Angular login screen has someone
to log in as. Idempotent: a no-op once any user exists.
"""
from __future__ import annotations

import os
import secrets

from django.core.management.base import BaseCommand

from apps.accounts.repositories import UserRepository


class Command(BaseCommand):
    help = "Create the single default operator account, if no user exists yet."

    def handle(self, *args, **options) -> None:
        repo = UserRepository()
        if repo.exists():
            self.stdout.write("An account already exists — nothing to seed.")
            return

        username = os.environ.get("MISBAH_ADMIN_USERNAME", "operator")
        password = os.environ.get("MISBAH_ADMIN_PASSWORD") or secrets.token_urlsafe(12)

        repo.create_superuser(username=username, password=password, email="")

        self.stdout.write(self.style.SUCCESS(f"Created operator account: {username}"))
        if "MISBAH_ADMIN_PASSWORD" not in os.environ:
            self.stdout.write(
                self.style.WARNING(
                    f"No MISBAH_ADMIN_PASSWORD set — generated password: {password}\n"
                    "Save it now; it is not stored anywhere and not shown again."
                )
            )
