import uuid

from fastapi.testclient import TestClient

from tests.conftest import envelope_data


def test_register_login_profile_refresh_logout(client: TestClient) -> None:
    email = f"user-{uuid.uuid4().hex[:12]}@example.com"
    password = "securepass1"

    register = client.post(
        "/auth/register",
        json={"email": email, "password": password, "display_name": "Test"},
    )
    assert register.status_code == 201, register.text
    tokens = envelope_data(register)
    assert tokens["token_type"] == "bearer"
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    profile = client.get(
        "/account/profile",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert profile.status_code == 200
    body = envelope_data(profile)
    assert body["email"] == email
    assert body["display_name"] == "Test"

    login = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    login_tokens = envelope_data(login)

    refreshed = client.post(
        "/auth/refresh-token",
        json={"refresh_token": login_tokens["refresh_token"]},
    )
    assert refreshed.status_code == 200
    new_tokens = envelope_data(refreshed)

    reuse = client.post(
        "/auth/refresh-token",
        json={"refresh_token": login_tokens["refresh_token"]},
    )
    assert reuse.status_code == 401
    assert reuse.json()["ok"] is False

    logout = client.post(
        "/auth/logout",
        json={"refresh_token": new_tokens["refresh_token"]},
    )
    assert logout.status_code == 200
    assert logout.json()["ok"] is True

    after_logout = client.post(
        "/auth/refresh-token",
        json={"refresh_token": new_tokens["refresh_token"]},
    )
    assert after_logout.status_code == 401


def test_register_duplicate_email(client: TestClient) -> None:
    email = f"dup-{uuid.uuid4().hex[:12]}@example.com"
    payload = {"email": email, "password": "securepass1"}
    assert client.post("/auth/register", json=payload).status_code == 201
    assert client.post("/auth/register", json=payload).status_code == 409


def test_login_wrong_password(client: TestClient) -> None:
    email = f"bad-{uuid.uuid4().hex[:12]}@example.com"
    client.post(
        "/auth/register",
        json={"email": email, "password": "securepass1"},
    )
    response = client.post(
        "/auth/login",
        json={"email": email, "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_profile_requires_auth(client: TestClient) -> None:
    assert client.get("/account/profile").status_code == 401
