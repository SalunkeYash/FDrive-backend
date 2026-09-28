import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient


def _auth_header(client: TestClient) -> dict[str, str]:
    email = f"files-{uuid.uuid4().hex[:12]}@example.com"
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "securepass1", "display_name": "File User"},
    )
    assert response.status_code == 201, response.text
    tokens = response.json()["data"]
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_request_upload_url_and_complete(client: TestClient) -> None:
    headers = _auth_header(client)
    size = 11

    with patch(
        "service.file_service.s3_store.create_presigned_upload_url",
        return_value="https://example.test/upload",
    ):
        requested = client.post(
            "/files/upload-url",
            headers=headers,
            json={
                "file_name": "hello.txt",
                "size_bytes": size,
                "mime_type": "text/plain",
            },
        )
    assert requested.status_code == 201, requested.text
    body = requested.json()["data"]
    file_id = body["file_id"]
    assert body["upload_url"] == "https://example.test/upload"
    assert body["required_headers"]["Content-Type"] == "text/plain"

    with patch(
        "service.file_service.s3_store.get_object_metadata",
        return_value={"ContentLength": size, "ETag": '"abc"', "ContentType": "text/plain"},
    ):
        completed = client.post(
            f"/files/{file_id}/complete-upload",
            headers=headers,
        )
    assert completed.status_code == 200, completed.text
    assert completed.json()["data"]["status"] == "ready"
    assert completed.json()["data"]["size_bytes"] == size

    listed = client.get("/files", headers=headers)
    assert listed.status_code == 200
    assert any(f["id"] == file_id for f in listed.json()["data"])

    usage = client.get("/account/storage-quota", headers=headers)
    assert usage.json()["data"]["bytes_used"] == size


def test_complete_upload_rejects_size_mismatch(client: TestClient) -> None:
    headers = _auth_header(client)

    with patch(
        "service.file_service.s3_store.create_presigned_upload_url",
        return_value="https://example.test/upload",
    ):
        requested = client.post(
            "/files/upload-url",
            headers=headers,
            json={"file_name": "bad.txt", "size_bytes": 10, "mime_type": "text/plain"},
        )
    file_id = requested.json()["data"]["file_id"]

    with patch(
        "service.file_service.s3_store.get_object_metadata",
        return_value={"ContentLength": 99, "ETag": '"x"'},
    ):
        failed = client.post(
            f"/files/{file_id}/complete-upload",
            headers=headers,
        )
    assert failed.status_code == 400


def test_quota_blocks_oversized_upload_request(client: TestClient) -> None:
    headers = _auth_header(client)
    huge = 5 * 1024 * 1024 * 1024 + 1
    response = client.post(
        "/files/upload-url",
        headers=headers,
        json={"file_name": "huge.bin", "size_bytes": huge},
    )
    assert response.status_code == 413


def _create_ready_file(client: TestClient, headers: dict[str, str], size: int = 5) -> str:
    with patch(
        "service.file_service.s3_store.create_presigned_upload_url",
        return_value="https://example.test/upload",
    ):
        requested = client.post(
            "/files/upload-url",
            headers=headers,
            json={
                "file_name": "notes.txt",
                "size_bytes": size,
                "mime_type": "text/plain",
            },
        )
    file_id = requested.json()["data"]["file_id"]
    with patch(
        "service.file_service.s3_store.get_object_metadata",
        return_value={
            "ContentLength": size,
            "ETag": '"abc"',
            "ContentType": "text/plain",
        },
    ):
        completed = client.post(
            f"/files/{file_id}/complete-upload",
            headers=headers,
        )
    assert completed.status_code == 200
    return file_id


def test_request_download_url(client: TestClient) -> None:
    headers = _auth_header(client)
    file_id = _create_ready_file(client, headers)

    with patch(
        "service.file_service.s3_store.create_presigned_download_url",
        return_value="https://example.test/download",
    ):
        response = client.get(
            f"/files/{file_id}/download-url",
            headers=headers,
        )
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["download_url"] == "https://example.test/download"
    assert body["download_method"] == "GET"
    assert body["file_name"] == "notes.txt"
    assert body["file_id"] == file_id


def test_download_rejects_pending_file(client: TestClient) -> None:
    headers = _auth_header(client)
    with patch(
        "service.file_service.s3_store.create_presigned_upload_url",
        return_value="https://example.test/upload",
    ):
        requested = client.post(
            "/files/upload-url",
            headers=headers,
            json={"file_name": "pending.txt", "size_bytes": 3},
        )
    file_id = requested.json()["data"]["file_id"]
    response = client.get(
        f"/files/{file_id}/download-url",
        headers=headers,
    )
    assert response.status_code == 400


def test_rename_move_and_copy_file(client: TestClient) -> None:
    headers = _auth_header(client)
    file_id = _create_ready_file(client, headers, size=5)

    renamed = client.patch(
        f"/files/{file_id}",
        headers=headers,
        json={"file_name": "renamed.txt"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["data"]["name"] == "renamed.txt"

    folder = client.post(
        "/folders",
        headers=headers,
        json={"name": "Inbox"},
    )
    folder_id = folder.json()["data"]["id"]

    moved = client.post(
        f"/files/{file_id}/move",
        headers=headers,
        json={"destination_folder_id": folder_id},
    )
    assert moved.status_code == 200
    assert moved.json()["data"]["folder_id"] == folder_id

    with patch("service.file_service.s3_store.copy_object") as copy_mock:
        copied = client.post(
            f"/files/{file_id}/copy",
            headers=headers,
            json={
                "destination_folder_id": None,
                "new_file_name": "renamed-copy.txt",
            },
        )
    assert copied.status_code == 201, copied.text
    assert copied.json()["data"]["name"] == "renamed-copy.txt"
    assert copied.json()["data"]["folder_id"] is None
    assert copied.json()["data"]["id"] != file_id
    copy_mock.assert_called_once()

    usage = client.get("/account/storage-quota", headers=headers)
    assert usage.json()["data"]["bytes_used"] == 10  # original + copy
