from __future__ import annotations

from typing import Any

import pytest

from mesbah.database import django_database


def test_the_embedded_server_socket_url() -> None:
    settings: dict[str, Any] = django_database(
        "postgresql://postgres:@/postgres?host=/home/sara/.local/share/mesbah/postgres"
    )

    assert settings["NAME"] == "postgres"
    assert settings["USER"] == "postgres"
    assert settings["PASSWORD"] == ""
    assert settings["HOST"] == "/home/sara/.local/share/mesbah/postgres"
    assert settings["CONN_MAX_AGE"] == 0
    assert "pool" in settings["OPTIONS"]


def test_an_external_server_url() -> None:
    settings: dict[str, Any] = django_database("postgres://app:p%40ss@db.internal:6543/mesbah")

    assert (settings["HOST"], settings["PORT"]) == ("db.internal", "6543")
    assert settings["PASSWORD"] == "p@ss"
    assert settings["NAME"] == "mesbah"


def test_anything_but_postgres_is_refused() -> None:
    with pytest.raises(ValueError, match="PostgreSQL"):
        django_database("sqlite:///mesbah.db")
