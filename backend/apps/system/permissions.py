from __future__ import annotations

from rest_framework.permissions import IsAdminUser


class CanManageSystem(IsAdminUser):
    message: str = "You don't have access to this."
