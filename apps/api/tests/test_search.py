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


def test_search_files_and_folders(client: TestClient) -> None:
    headers = _register(client, f"search-{uuid.uuid4().hex[:8]}@example.com")

    folder = client.post(
        "/api/v1/folders/create-folder",
        headers=headers,
        json={"name": "Reports Q1"},
    )
    assert folder.status_code == 201, folder.text

    with patch(
        "app.services.files.s3_store.create_presigned_upload_url",
        return_value="https://example.test/upload",
    ):
        requested = client.post(
            "/api/v1/files/request-upload-url",
            headers=headers,
            json={
                "file_name": "annual-report.pdf",
                "size_bytes": 8,
                "mime_type": "application/pdf",
            },
        )
    file_id = requested.json()["file_id"]
    with patch(
        "app.services.files.s3_store.get_object_metadata",
        return_value={"ContentLength": 8, "ETag": '"x"', "ContentType": "application/pdf"},
    ):
        assert (
            client.post(
                f"/api/v1/files/{file_id}/complete-upload",
                headers=headers,
            ).status_code
            == 200
        )

    found = client.get("/api/v1/search/search-drive", headers=headers, params={"q": "report"})
    assert found.status_code == 200, found.text
    body = found.json()
    assert body["query"] == "report"
    assert any(f["name"] == "annual-report.pdf" for f in body["files"])
    assert any(f["name"] == "Reports Q1" for f in body["folders"])

    empty = client.get("/api/v1/search/search-drive", headers=headers, params={"q": "zzzzmissing"})
    assert empty.status_code == 200
    assert empty.json()["files"] == []
    assert empty.json()["folders"] == []
