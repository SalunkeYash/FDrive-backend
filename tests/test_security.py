import pytest
from fastapi.testclient import TestClient

from dependencies import rate_limit


def test_security_headers_present(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "no-referrer"


def test_auth_rate_limit_blocks_bursts(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rate_limit.settings, "auth_rate_limit_per_minute", 2)
    monkeypatch.setattr(rate_limit, "get_redis", lambda: None)
    rate_limit._memory_hits.clear()

    for _ in range(2):
        response = client.post(
            "/auth/login",
            json={"email": "nobody@example.com", "password": "wrongpass"},
        )
        assert response.status_code in {401, 429}

    blocked = client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "wrongpass"},
    )
    assert blocked.status_code == 429
