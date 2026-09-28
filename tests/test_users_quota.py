import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.models import User
from app.services import quota


def _auth_header(client: TestClient) -> dict[str, str]:
    email = f"quota-{uuid.uuid4().hex[:12]}@example.com"
    response = client.post(
        "/api/v1/auth/register-account",
        json={"email": email, "password": "securepass1", "display_name": "Quota User"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_get_profile_and_storage_quota(client: TestClient) -> None:
    headers = _auth_header(client)

    profile = client.get("/api/v1/account/profile", headers=headers)
    assert profile.status_code == 200
    body = profile.json()
    assert body["bytes_used"] == 0
    assert body["bytes_limit"] == 5 * 1024 * 1024 * 1024

    quota_response = client.get("/api/v1/account/storage-quota", headers=headers)
    assert quota_response.status_code == 200
    data = quota_response.json()
    assert data["bytes_used"] == 0
    assert data["bytes_remaining"] == data["bytes_limit"]
    assert data["usage_percent"] == 0.0


def test_update_profile(client: TestClient) -> None:
    headers = _auth_header(client)
    updated = client.patch(
        "/api/v1/account/profile",
        headers=headers,
        json={"display_name": "New Name"},
    )
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "New Name"


def test_quota_helpers_add_and_release() -> None:
    user = User(email="x@example.com", bytes_used=100, bytes_limit=200)

    assert quota.has_room(user, 50) is True
    assert quota.has_room(user, 150) is False
    assert quota.bytes_remaining(user) == 100

    quota.add_bytes_used(user, 50)
    assert user.bytes_used == 150

    with pytest.raises(HTTPException) as blocked:
        quota.add_bytes_used(user, 100)
    assert blocked.value.status_code == 413

    quota.release_bytes_used(user, 200)
    assert user.bytes_used == 0


def test_ensure_quota_blocks_overflow() -> None:
    user = User(email="y@example.com", bytes_used=90, bytes_limit=100)
    with pytest.raises(HTTPException) as blocked:
        quota.ensure_quota(user, 20)
    assert blocked.value.status_code == 413
