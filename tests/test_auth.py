import uuid

from fastapi.testclient import TestClient


def test_register_login_profile_refresh_logout(client: TestClient) -> None:
    email = f"user-{uuid.uuid4().hex[:12]}@example.com"
    password = "securepass1"

    register = client.post(
        "/api/v1/auth/register-account",
        json={"email": email, "password": password, "display_name": "Test"},
    )
    assert register.status_code == 201, register.text
    tokens = register.json()
    assert tokens["token_type"] == "bearer"
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    profile = client.get(
        "/api/v1/account/profile",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert profile.status_code == 200
    body = profile.json()
    assert body["email"] == email
    assert body["display_name"] == "Test"

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    login_tokens = login.json()

    refreshed = client.post(
        "/api/v1/auth/refresh-token",
        json={"refresh_token": login_tokens["refresh_token"]},
    )
    assert refreshed.status_code == 200
    new_tokens = refreshed.json()

    reuse = client.post(
        "/api/v1/auth/refresh-token",
        json={"refresh_token": login_tokens["refresh_token"]},
    )
    assert reuse.status_code == 401

    logout = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": new_tokens["refresh_token"]},
    )
    assert logout.status_code == 204

    after_logout = client.post(
        "/api/v1/auth/refresh-token",
        json={"refresh_token": new_tokens["refresh_token"]},
    )
    assert after_logout.status_code == 401


def test_register_duplicate_email(client: TestClient) -> None:
    email = f"dup-{uuid.uuid4().hex[:12]}@example.com"
    payload = {"email": email, "password": "securepass1"}
    assert client.post("/api/v1/auth/register-account", json=payload).status_code == 201
    assert client.post("/api/v1/auth/register-account", json=payload).status_code == 409


def test_login_wrong_password(client: TestClient) -> None:
    email = f"bad-{uuid.uuid4().hex[:12]}@example.com"
    client.post(
        "/api/v1/auth/register-account",
        json={"email": email, "password": "securepass1"},
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_profile_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/account/profile").status_code == 401
