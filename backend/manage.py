#!/usr/bin/env python
"""Django's command-line utility for administrative tasks.

This is the Django/DRF side of Mesbah's in-progress backend migration — see
the root plan and backend/apps/common/CLAUDE.md. It is independent of
`backend/app/` (FastAPI), which is what the Angular frontend actually talks
to today; do not remove that until this side reaches feature parity.
"""
import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Could not import Django. Is it installed and is the virtual environment active? "
            "Install backend/requirements-django.txt."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
