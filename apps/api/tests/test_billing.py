import uuid

from fastapi.testclient import TestClient


def test_list_plans_and_current_plan(client: TestClient) -> None:
    plans = client.get("/api/v1/billing/list-plans")
    assert plans.status_code == 200
    assert len(plans.json()["plans"]) >= 2

    email = f"bill-{uuid.uuid4().hex[:8]}@example.com"
    registered = client.post(
        "/api/v1/auth/register-account",
        json={"email": email, "password": "securepass1", "display_name": "Bill"},
    )
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

    current = client.get("/api/v1/billing/current-plan", headers=headers)
    assert current.status_code == 200
    assert current.json()["bytes_limit"] > 0

    portal = client.post(
        "/api/v1/billing/create-billing-portal-session",
        headers=headers,
        json={"return_url": "http://localhost:5173/drive"},
    )
    assert portal.status_code == 200
    assert portal.json()["status"] == "stub"
