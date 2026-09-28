import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient


def _register(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register-account",
        json={
            "email": f"mp-{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepass1",
            "display_name": "Uploader",
        },
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_multipart_initiate_part_and_complete(client: TestClient) -> None:
    headers = _register(client)

    with patch(
        "app.services.multipart_uploads.s3_store.initiate_multipart_upload",
        return_value="upload-xyz",
    ):
        initiated = client.post(
            "/api/v1/uploads/initiate-multipart-upload",
            headers=headers,
            json={
                "file_name": "big.bin",
                "size_bytes": 10 * 1024 * 1024,
                "mime_type": "application/octet-stream",
                "part_size_bytes": 5 * 1024 * 1024,
            },
        )
    assert initiated.status_code == 201, initiated.text
    body = initiated.json()
    session_id = body["upload_session_id"]
    assert body["s3_upload_id"] == "upload-xyz"
    assert body["total_parts"] == 2

    with patch(
        "app.services.multipart_uploads.s3_store.create_presigned_part_upload_url",
        return_value="https://example.test/part/1",
    ):
        part = client.post(
            f"/api/v1/uploads/{session_id}/get-part-upload-url",
            headers=headers,
            json={"part_number": 1},
        )
    assert part.status_code == 200
    assert part.json()["upload_url"].endswith("/part/1")

    with (
        patch("app.services.multipart_uploads.s3_store.complete_multipart_upload"),
        patch(
            "app.services.multipart_uploads.s3_store.get_object_metadata",
            return_value={
                "ContentLength": 10 * 1024 * 1024,
                "ETag": '"done"',
            },
        ),
        patch("app.services.multipart_uploads.enqueue_job", return_value="msg"),
    ):
        done = client.post(
            f"/api/v1/uploads/{session_id}/complete-multipart-upload",
            headers=headers,
            json={
                "parts": [
                    {"part_number": 1, "etag": '"a"'},
                    {"part_number": 2, "etag": '"b"'},
                ]
            },
        )
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "ready"
    assert done.json()["name"] == "big.bin"


def test_multipart_abort(client: TestClient) -> None:
    headers = _register(client)

    with patch(
        "app.services.multipart_uploads.s3_store.initiate_multipart_upload",
        return_value="upload-abort",
    ):
        initiated = client.post(
            "/api/v1/uploads/initiate-multipart-upload",
            headers=headers,
            json={
                "file_name": "abort.bin",
                "size_bytes": 6 * 1024 * 1024,
                "part_size_bytes": 5 * 1024 * 1024,
            },
        )
    session_id = initiated.json()["upload_session_id"]

    with patch("app.services.multipart_uploads.s3_store.abort_multipart_upload") as abort:
        response = client.post(
            f"/api/v1/uploads/{session_id}/abort-multipart-upload",
            headers=headers,
        )
    assert response.status_code == 204
    abort.assert_called_once()
