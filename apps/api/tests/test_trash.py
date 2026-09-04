import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient


def _auth_header(client: TestClient) -> dict[str, str]:
    email = f"trash-{uuid.uuid4().hex[:12]}@example.com"
    response = client.post(
        "/api/v1/auth/register-account",
        json={"email": email, "password": "securepass1", "display_name": "Trash User"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _ready_file(client: TestClient, headers: dict[str, str], name: str = "doc.txt") -> str:
    with patch(
        "app.services.files.s3_store.create_presigned_upload_url",
        return_value="https://example.test/upload",
    ):
        requested = client.post(
            "/api/v1/files/request-upload-url",
            headers=headers,
            json={"file_name": name, "size_bytes": 4, "mime_type": "text/plain"},
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


def test_file_trash_restore_and_permanent_delete(client: TestClient) -> None:
    headers = _auth_header(client)
    file_id = _ready_file(client, headers)

    trashed = client.post(
        f"/api/v1/trash/files/{file_id}/move-file-to-trash",
        headers=headers,
    )
    assert trashed.status_code == 200
    assert trashed.json()["is_trashed"] is True

    listing = client.get("/api/v1/files/list-folder-files", headers=headers)
    assert all(f["id"] != file_id for f in listing.json())

    trash = client.get("/api/v1/trash/list-trash-items", headers=headers)
    assert any(i["resource_id"] == file_id for i in trash.json()["items"])

    restored = client.post(
        f"/api/v1/trash/files/{file_id}/restore-file-from-trash",
        headers=headers,
    )
    assert restored.status_code == 200
    assert restored.json()["is_trashed"] is False

    client.post(f"/api/v1/trash/files/{file_id}/move-file-to-trash", headers=headers)
    with patch("app.services.trash.s3_store.delete_object") as delete_mock:
        deleted = client.post(
            f"/api/v1/trash/files/{file_id}/permanently-delete-file",
            headers=headers,
        )
    assert deleted.status_code == 204
    delete_mock.assert_called_once()

    usage = client.get("/api/v1/account/storage-quota", headers=headers)
    assert usage.json()["bytes_used"] == 0


def test_folder_trash_and_restore(client: TestClient) -> None:
    headers = _auth_header(client)
    folder = client.post(
        "/api/v1/folders/create-folder",
        headers=headers,
        json={"name": "Temp"},
    )
    folder_id = folder.json()["id"]

    trashed = client.post(
        f"/api/v1/trash/folders/{folder_id}/move-folder-to-trash",
        headers=headers,
    )
    assert trashed.status_code == 200
    assert trashed.json()["is_trashed"] is True

    missing = client.get(f"/api/v1/folders/{folder_id}/get-folder", headers=headers)
    assert missing.status_code == 404

    restored = client.post(
        f"/api/v1/trash/folders/{folder_id}/restore-folder-from-trash",
        headers=headers,
    )
    assert restored.status_code == 200
    assert restored.json()["is_trashed"] is False

    found = client.get(f"/api/v1/folders/{folder_id}/get-folder", headers=headers)
    assert found.status_code == 200
