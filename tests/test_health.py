from fastapi.testclient import TestClient

from main import app
from tests.conftest import envelope_data

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = envelope_data(response)
    assert body["status"] == "ok"
    assert body["service"] == "fdrive-api"


def test_ready_shape() -> None:
    """Ready always returns structured checks; status depends on DB availability."""
    response = client.get("/ready")
    assert response.status_code in (200, 503)
    body = response.json()
    assert body["ok"] is (response.status_code == 200)
    data = body.get("data") or {}
    assert "checks" in data
    assert "database" in data["checks"]
    assert data["status"] in ("ready", "not_ready")
