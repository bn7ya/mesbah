from __future__ import annotations

import pytest
from pytest_django.fixtures import Settings

from contracts import Contract


@pytest.fixture(autouse=True)
def _own_cache(settings: Settings) -> None:
    # Tests share Redis with a running dev server; a cache of their own keeps its entries out.
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-contracts",
        action="store_true",
        help="rewrite backend/contracts/ from the code instead of comparing with it",
    )


@pytest.fixture
def contract(request: pytest.FixtureRequest) -> Contract:
    return Contract(bool(request.config.getoption("--update-contracts")))
