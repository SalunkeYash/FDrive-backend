from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from dependencies import rate_limit
from integrations.redis_client import get_redis
from main import app


@pytest.fixture(autouse=True)
def _relax_auth_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rate_limit.settings, "auth_rate_limit_per_minute", 10_000)
    rate_limit._memory_hits.clear()
    client = get_redis()
    if client is not None:
        try:
            for key in client.scan_iter("auth-rate:*"):
                client.delete(key)
        except Exception:
            pass


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


def envelope_data(response) -> dict | list | None:
    """Assert company-style envelope and return data payload."""
    body = response.json()
    assert "ok" in body, body
    if response.status_code < 400:
        assert body["ok"] is True, body
    return body.get("data")
