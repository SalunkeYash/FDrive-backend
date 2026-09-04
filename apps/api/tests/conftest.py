from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.core import rate_limit
from app.main import app


@pytest.fixture(autouse=True)
def _relax_auth_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rate_limit.settings, "auth_rate_limit_per_minute", 10_000)
    rate_limit._memory_hits.clear()


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
