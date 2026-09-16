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


def test_grantee_viewer_and_editor_access(client: TestClient) -> None:
    owner = _register(client, f"owner-{uuid.uuid4().hex[:8]}@example.com")
    viewer_email = f"view-{uuid.uuid4().hex[:8]}@example.com"
    editor_email = f"edit-{uuid.uuid4().hex[:8]}@example.com"
    viewer = _register(client, viewer_email)
    editor = _register(client, editor_email)
    file_id = _ready_file(client, owner)

    assert (
        client.post(
            "/api/v1/shares/create-user-share",
            headers=owner,
            json={
                "resource_type": "file",
                "resource_id": file_id,
                "grantee_email": viewer_email,
                "role": "viewer",
            },
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/v1/shares/create-user-share",
            headers=owner,
            json={
                "resource_type": "file",
                "resource_id": file_id,
                "grantee_email": editor_email,
                "role": "editor",
            },
        ).status_code
        == 201
    )

    shared = client.get("/api/v1/shares/list-shared-with-me", headers=viewer)
    assert shared.status_code == 200
    assert any(i["resource_id"] == file_id for i in shared.json())

    assert (
        client.get(f"/api/v1/files/{file_id}/get-file", headers=viewer).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/files/{file_id}/request-download-url", headers=viewer
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/files/{file_id}/rename-file",
            headers=viewer,
            json={"file_name": "nope.txt"},
        ).status_code
        == 404
    )

    renamed = client.patch(
        f"/api/v1/files/{file_id}/rename-file",
        headers=editor,
        json={"file_name": "edited.txt"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "edited.txt"


def test_shared_folder_editor_can_list_and_rename(client: TestClient) -> None:
    owner = _register(client, f"owner-{uuid.uuid4().hex[:8]}@example.com")
    editor_email = f"edit-{uuid.uuid4().hex[:8]}@example.com"
    editor = _register(client, editor_email)

    folder = client.post(
        "/api/v1/folders/create-folder",
        headers=owner,
        json={"name": "Shared Docs"},
    )
    assert folder.status_code == 201, folder.text
    folder_id = folder.json()["id"]

    file_id = _ready_file(client, owner)
    moved = client.post(
        f"/api/v1/files/{file_id}/move-file",
        headers=owner,
        json={"destination_folder_id": folder_id},
    )
    assert moved.status_code == 200, moved.text

    assert (
        client.post(
            "/api/v1/shares/create-user-share",
            headers=owner,
            json={
                "resource_type": "folder",
                "resource_id": folder_id,
                "grantee_email": editor_email,
                "role": "editor",
            },
        ).status_code
        == 201
    )

    listed = client.get(
        "/api/v1/files/list-folder-files",
        headers=editor,
        params={"folder_id": folder_id},
    )
    assert listed.status_code == 200
    assert any(f["id"] == file_id for f in listed.json())

    renamed = client.patch(
        f"/api/v1/folders/{folder_id}/rename-folder",
        headers=editor,
        json={"name": "Team Docs"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "Team Docs"
