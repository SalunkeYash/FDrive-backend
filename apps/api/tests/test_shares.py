import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient


def _register(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register-account",
        json={"email": email, "password": "securepass1", "display_name": "User"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _ready_file(client: TestClient, headers: dict[str, str]) -> str:
    with patch(
        "app.services.files.s3_store.create_presigned_upload_url",
        return_value="https://example.test/upload",
    ):
        requested = client.post(
            "/api/v1/files/request-upload-url",
            headers=headers,
            json={"file_name": "shared.txt", "size_bytes": 4, "mime_type": "text/plain"},
        )
    file_id = requested.json()["file_id"]
    with patch(
        "app.services.files.s3_store.get_object_metadata",
        return_value={"ContentLength": 4, "ETag": '"a"', "ContentType": "text/plain"},
    ):
        assert (
            client.post(
                f"/api/v1/files/{file_id}/complete-upload",
                headers=headers,
            ).status_code
            == 200
        )
    return file_id


def test_create_user_share_and_list(client: TestClient) -> None:
    owner = _register(client, f"owner-{uuid.uuid4().hex[:8]}@example.com")
    grantee_email = f"peer-{uuid.uuid4().hex[:8]}@example.com"
    _register(client, grantee_email)
    file_id = _ready_file(client, owner)

    created = client.post(
        "/api/v1/shares/create-user-share",
        headers=owner,
        json={
            "resource_type": "file",
            "resource_id": file_id,
            "grantee_email": grantee_email,
            "role": "viewer",
        },
    )
    assert created.status_code == 201, created.text
    share_id = created.json()["id"]

    mine = client.get("/api/v1/shares/list-my-shares", headers=owner)
    assert mine.status_code == 200
    assert any(s["id"] == share_id for s in mine.json())

    revoked = client.post(
        f"/api/v1/shares/{share_id}/revoke-share",
        headers=owner,
    )
    assert revoked.status_code == 204


def test_create_link_share_and_access(client: TestClient) -> None:
    owner = _register(client, f"link-{uuid.uuid4().hex[:8]}@example.com")
    file_id = _ready_file(client, owner)

    created = client.post(
        "/api/v1/shares/create-link-share",
        headers=owner,
        json={"resource_type": "file", "resource_id": file_id, "role": "viewer"},
    )
    assert created.status_code == 201, created.text
    token = created.json()["token"]
    assert token

    accessed = client.get(f"/api/v1/shares/access-shared-link/{token}")
    assert accessed.status_code == 200
    assert accessed.json()["resource_id"] == file_id
    assert accessed.json()["resource_name"] == "shared.txt"
