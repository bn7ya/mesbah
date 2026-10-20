from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from apps.accounts.services import SetupService
from apps.accounts.services.setup_code import current_code


class Command(BaseCommand):
    help = "Print the one-time code that creates the owner account, while Mesbah has none."

    def handle(self, *args: Any, **options: Any) -> None:
        if not SetupService().needed():
            self.stdout.write("Mesbah is already set up.")
            return
        self.stdout.write(current_code())
