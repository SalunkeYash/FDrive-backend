import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient


def _register(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "securepass1", "display_name": "User"},
    )
    assert response.status_code == 201, response.text
    tokens = response.json()["data"]
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _ready_file(client: TestClient, headers: dict[str, str]) -> str:
    with patch(
        "service.file_service.s3_store.create_presigned_upload_url",
        return_value="https://example.test/upload",
    ):
        requested = client.post(
            "/files/upload-url",
            headers=headers,
            json={"file_name": "shared.txt", "size_bytes": 4, "mime_type": "text/plain"},
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


def test_create_user_share_and_list(client: TestClient) -> None:
    owner = _register(client, f"owner-{uuid.uuid4().hex[:8]}@example.com")
    grantee_email = f"peer-{uuid.uuid4().hex[:8]}@example.com"
    _register(client, grantee_email)
    file_id = _ready_file(client, owner)

    created = client.post(
        "/shares/user",
        headers=owner,
        json={
            "resource_type": "file",
            "resource_id": file_id,
            "grantee_email": grantee_email,
            "role": "viewer",
        },
    )
    assert created.status_code == 201, created.text
    share_id = created.json()["data"]["id"]

    mine = client.get("/shares/mine", headers=owner)
    assert mine.status_code == 200
    assert any(s["id"] == share_id for s in mine.json()["data"])

    revoked = client.post(
        f"/shares/{share_id}/revoke",
        headers=owner,
    )
    assert revoked.status_code == 200


def test_create_link_share_and_access(client: TestClient) -> None:
    owner = _register(client, f"link-{uuid.uuid4().hex[:8]}@example.com")
    file_id = _ready_file(client, owner)

    created = client.post(
        "/shares/link",
        headers=owner,
        json={"resource_type": "file", "resource_id": file_id, "role": "viewer"},
    )
    assert created.status_code == 201, created.text
    token = created.json()["data"]["token"]
    assert token

    accessed = client.get(f"/shares/link/{token}")
    assert accessed.status_code == 200
    assert accessed.json()["data"]["resource_id"] == file_id
    assert accessed.json()["data"]["resource_name"] == "shared.txt"

    contents = client.get(f"/shares/link/{token}/contents")
    assert contents.status_code == 200, contents.text
    body = contents.json()["data"]
    assert body["resource_type"] == "file"
    assert len(body["files"]) == 1
    assert body["files"][0]["id"] == file_id

    download = client.get(
        f"/shares/link/{token}/files/{file_id}/download-url"
    )
    assert download.status_code == 200, download.text
    assert "download_url" in download.json()["data"]


def test_set_link_access_restricted_and_anyone(client: TestClient) -> None:
    owner = _register(client, f"gen-{uuid.uuid4().hex[:8]}@example.com")
    file_id = _ready_file(client, owner)

    anyone = client.post(
        "/shares/link-access",
        headers=owner,
        json={
            "resource_type": "file",
            "resource_id": file_id,
            "access": "anyone",
            "role": "viewer",
        },
    )
    assert anyone.status_code == 200, anyone.text
    assert anyone.json()["data"]["link"]["enabled"] is True
    token = anyone.json()["data"]["link"]["token"]
    assert token

    access = client.get(
        "/shares/resource-access",
        headers=owner,
        params={"resource_type": "file", "resource_id": file_id},
    )
    assert access.status_code == 200
    assert access.json()["data"]["link"]["enabled"] is True
    assert access.json()["data"]["owner"]["role"] == "owner"

    restricted = client.post(
        "/shares/link-access",
        headers=owner,
        json={
            "resource_type": "file",
            "resource_id": file_id,
            "access": "restricted",
            "role": "viewer",
        },
    )
    assert restricted.status_code == 200, restricted.text
    assert restricted.json()["data"]["link"]["enabled"] is False

    assert (
        client.get(f"/shares/link/{token}").status_code
        == 404
    )


def test_link_share_folder_contents(client: TestClient) -> None:
    owner = _register(client, f"foldlink-{uuid.uuid4().hex[:8]}@example.com")
    folder = client.post(
        "/folders",
        headers=owner,
        json={"name": "Public Pics"},
    )
    assert folder.status_code == 201, folder.text
    folder_id = folder.json()["data"]["id"]

    file_id = _ready_file(client, owner)
    assert (
        client.post(
            f"/files/{file_id}/move",
            headers=owner,
            json={"destination_folder_id": folder_id},
        ).status_code
        == 200
    )

    link = client.post(
        "/shares/link-access",
        headers=owner,
        json={
            "resource_type": "folder",
            "resource_id": folder_id,
            "access": "anyone",
            "role": "viewer",
        },
    )
    assert link.status_code == 200, link.text
    token = link.json()["data"]["link"]["token"]

    contents = client.get(f"/shares/link/{token}/contents")
    assert contents.status_code == 200, contents.text
    assert any(f["id"] == file_id for f in contents.json()["data"]["files"])


def test_grantee_viewer_and_editor_access(client: TestClient) -> None:
    owner = _register(client, f"owner-{uuid.uuid4().hex[:8]}@example.com")
    viewer_email = f"view-{uuid.uuid4().hex[:8]}@example.com"
    editor_email = f"edit-{uuid.uuid4().hex[:8]}@example.com"
    viewer = _register(client, viewer_email)
    editor = _register(client, editor_email)
    file_id = _ready_file(client, owner)

    assert (
        client.post(
            "/shares/user",
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
            "/shares/user",
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

    shared = client.get("/shares/shared-with-me", headers=viewer)
    assert shared.status_code == 200
    assert any(i["resource_id"] == file_id for i in shared.json()["data"])

    assert (
        client.get(f"/files/{file_id}", headers=viewer).status_code
        == 200
    )
    assert (
        client.get(
            f"/files/{file_id}/download-url", headers=viewer
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/files/{file_id}",
            headers=viewer,
            json={"file_name": "nope.txt"},
        ).status_code
        == 404
    )

    renamed = client.patch(
        f"/files/{file_id}",
        headers=editor,
        json={"file_name": "edited.txt"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["name"] == "edited.txt"


def test_shared_folder_editor_can_list_and_rename(client: TestClient) -> None:
    owner = _register(client, f"owner-{uuid.uuid4().hex[:8]}@example.com")
    editor_email = f"edit-{uuid.uuid4().hex[:8]}@example.com"
    editor = _register(client, editor_email)

    folder = client.post(
        "/folders",
        headers=owner,
        json={"name": "Shared Docs"},
    )
    assert folder.status_code == 201, folder.text
    folder_id = folder.json()["data"]["id"]

    file_id = _ready_file(client, owner)
    moved = client.post(
        f"/files/{file_id}/move",
        headers=owner,
        json={"destination_folder_id": folder_id},
    )
    assert moved.status_code == 200, moved.text

    assert (
        client.post(
            "/shares/user",
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
        "/files",
        headers=editor,
        params={"folder_id": folder_id},
    )
    assert listed.status_code == 200
    assert any(f["id"] == file_id for f in listed.json()["data"])

    renamed = client.patch(
        f"/folders/{folder_id}",
        headers=editor,
        json={"name": "Team Docs"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["name"] == "Team Docs"
