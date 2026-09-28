from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "fdrive-api"


def test_ready_shape() -> None:
    """Ready always returns structured checks; status depends on DB availability."""
    response = client.get("/ready")
    assert response.status_code in (200, 503)
    body = response.json()
    assert "checks" in body
    assert "database" in body["checks"]
    assert body["status"] in ("ready", "not_ready")


def test_api_v1_health() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
