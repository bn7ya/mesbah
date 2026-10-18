import pytest
from pytest_django.fixtures import Settings


@pytest.fixture(autouse=True)
def _own_cache(settings: Settings) -> None:
    # Tests share Redis with a running dev server; a cache of their own keeps its entries out.
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
