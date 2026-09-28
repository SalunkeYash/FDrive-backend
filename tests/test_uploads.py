import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient


def _register(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/register",
        json={
            "email": f"mp-{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepass1",
            "display_name": "Uploader",
        },
    )
    assert response.status_code == 201, response.text
    tokens = response.json()["data"]
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_multipart_initiate_part_and_complete(client: TestClient) -> None:
    headers = _register(client)

    with patch(
        "service.multipart_upload_service.s3_store.initiate_multipart_upload",
        return_value="upload-xyz",
    ):
        initiated = client.post(
            "/uploads/multipart",
            headers=headers,
            json={
                "file_name": "big.bin",
                "size_bytes": 10 * 1024 * 1024,
                "mime_type": "application/octet-stream",
                "part_size_bytes": 5 * 1024 * 1024,
            },
        )
    assert initiated.status_code == 201, initiated.text
    body = initiated.json()["data"]
    session_id = body["upload_session_id"]
    assert body["s3_upload_id"] == "upload-xyz"
    assert body["total_parts"] == 2

    with patch(
        "service.multipart_upload_service.s3_store.create_presigned_part_upload_url",
        return_value="https://example.test/part/1",
    ):
        part = client.post(
            f"/uploads/{session_id}/parts",
            headers=headers,
            json={"part_number": 1},
        )
    assert part.status_code == 200
    assert part.json()["data"]["upload_url"].endswith("/part/1")

    with (
        patch("service.multipart_upload_service.s3_store.complete_multipart_upload"),
        patch(
            "service.multipart_upload_service.s3_store.get_object_metadata",
            return_value={
                "ContentLength": 10 * 1024 * 1024,
                "ETag": '"done"',
            },
        ),
        patch("service.multipart_upload_service.enqueue_job", return_value="msg"),
    ):
        done = client.post(
            f"/uploads/{session_id}/complete",
            headers=headers,
            json={
                "parts": [
                    {"part_number": 1, "etag": '"a"'},
                    {"part_number": 2, "etag": '"b"'},
                ]
            },
        )
    assert done.status_code == 200, done.text
    assert done.json()["data"]["status"] == "ready"
    assert done.json()["data"]["name"] == "big.bin"


def test_multipart_abort(client: TestClient) -> None:
    headers = _register(client)

    with patch(
        "service.multipart_upload_service.s3_store.initiate_multipart_upload",
        return_value="upload-abort",
    ):
        initiated = client.post(
            "/uploads/multipart",
            headers=headers,
            json={
                "file_name": "abort.bin",
                "size_bytes": 6 * 1024 * 1024,
                "part_size_bytes": 5 * 1024 * 1024,
            },
        )
    session_id = initiated.json()["data"]["upload_session_id"]

    with patch("service.multipart_upload_service.s3_store.abort_multipart_upload") as abort:
        response = client.post(
            f"/uploads/{session_id}/abort",
            headers=headers,
        )
    assert response.status_code == 200
    abort.assert_called_once()
