import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient


def _auth_header(client: TestClient) -> dict[str, str]:
    email = f"trash-{uuid.uuid4().hex[:12]}@example.com"
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "securepass1", "display_name": "Trash User"},
    )
    assert response.status_code == 201, response.text
    tokens = response.json()["data"]
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _ready_file(client: TestClient, headers: dict[str, str], name: str = "doc.txt") -> str:
    with patch(
        "service.file_service.s3_store.create_presigned_upload_url",
        return_value="https://example.test/upload",
    ):
        requested = client.post(
            "/files/upload-url",
            headers=headers,
            json={"file_name": name, "size_bytes": 4, "mime_type": "text/plain"},
        )
    file_id = requested.json()["data"]["file_id"]
    with patch(
        "service.file_service.s3_store.get_object_metadata",
        return_value={"ContentLength": 4, "ETag": '"a"', "ContentType": "text/plain"},
    ):
        assert (
            client.post(
                f"/files/{file_id}/complete-upload",
                headers=headers,
            ).status_code
            == 200
        )
    return file_id


def test_file_trash_restore_and_permanent_delete(client: TestClient) -> None:
    headers = _auth_header(client)
    file_id = _ready_file(client, headers)

    trashed = client.post(
        f"/trash/files/{file_id}",
        headers=headers,
    )
    assert trashed.status_code == 200
    assert trashed.json()["data"]["is_trashed"] is True

    listing = client.get("/files", headers=headers)
    assert all(f["id"] != file_id for f in listing.json()["data"])

    trash = client.get("/trash", headers=headers)
    assert any(i["resource_id"] == file_id for i in trash.json()["data"]["items"])

    restored = client.post(
        f"/trash/files/{file_id}/restore",
        headers=headers,
    )
    assert restored.status_code == 200
    assert restored.json()["data"]["is_trashed"] is False

    client.post(f"/trash/files/{file_id}", headers=headers)
    with patch("service.trash_service.s3_store.delete_object") as delete_mock:
        deleted = client.post(
            f"/trash/files/{file_id}/delete",
            headers=headers,
        )
    assert deleted.status_code == 200
    delete_mock.assert_called_once()

    usage = client.get("/account/storage-quota", headers=headers)
    assert usage.json()["data"]["bytes_used"] == 0


def test_folder_trash_and_restore(client: TestClient) -> None:
    headers = _auth_header(client)
    folder = client.post(
        "/folders",
        headers=headers,
        json={"name": "Temp"},
    )
    folder_id = folder.json()["data"]["id"]

    trashed = client.post(
        f"/trash/folders/{folder_id}",
        headers=headers,
    )
    assert trashed.status_code == 200
    assert trashed.json()["data"]["is_trashed"] is True

    missing = client.get(f"/folders/{folder_id}", headers=headers)
    assert missing.status_code == 404

    restored = client.post(
        f"/trash/folders/{folder_id}/restore",
        headers=headers,
    )
    assert restored.status_code == 200
    assert restored.json()["data"]["is_trashed"] is False

    found = client.get(f"/folders/{folder_id}", headers=headers)
    assert found.status_code == 200
