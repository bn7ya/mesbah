from __future__ import annotations

from apps.members.permissions import IsAdministrator


class CanManageSystem(IsAdministrator):
    pass
