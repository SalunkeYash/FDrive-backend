import uuid

from fastapi.testclient import TestClient


def _auth_header(client: TestClient) -> dict[str, str]:
    email = f"folders-{uuid.uuid4().hex[:12]}@example.com"
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "securepass1", "display_name": "Folder User"},
    )
    assert response.status_code == 201, response.text
    tokens = response.json()["data"]
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_create_list_rename_move_trash_folder(client: TestClient) -> None:
    headers = _auth_header(client)

    root = client.post(
        "/folders",
        headers=headers,
        json={"name": "Documents"},
    )
    assert root.status_code == 201, root.text
    root_id = root.json()["data"]["id"]
    assert root.json()["data"]["path"] == "/"

    child = client.post(
        "/folders",
        headers=headers,
        json={"name": "Work", "parent_folder_id": root_id},
    )
    assert child.status_code == 201
    child_id = child.json()["data"]["id"]
    assert root_id in child.json()["data"]["path"]

    listing = client.get(
        "/folders/contents",
        headers=headers,
        params={"parent_folder_id": root_id},
    )
    assert listing.status_code == 200
    assert len(listing.json()["data"]["folders"]) == 1
    assert listing.json()["data"]["folders"][0]["name"] == "Work"

    renamed = client.patch(
        f"/folders/{child_id}",
        headers=headers,
        json={"name": "Projects"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["data"]["name"] == "Projects"

    other_root = client.post(
        "/folders",
        headers=headers,
        json={"name": "Archive"},
    )
    other_id = other_root.json()["data"]["id"]

    moved = client.post(
        f"/folders/{child_id}/move",
        headers=headers,
        json={"destination_parent_folder_id": other_id},
    )
    assert moved.status_code == 200
    assert moved.json()["data"]["parent_id"] == other_id
    assert other_id in moved.json()["data"]["path"]

    tree = client.get("/folders/tree", headers=headers)
    assert tree.status_code == 200
    names = {node["name"] for node in tree.json()["data"]}
    assert "Documents" in names
    assert "Archive" in names

    trashed = client.post(
        f"/folders/{other_id}/trash",
        headers=headers,
    )
    assert trashed.status_code == 200
    assert trashed.json()["data"]["is_trashed"] is True

    # Trashed branch no longer listed at root or in tree
    root_listing = client.get("/folders/contents", headers=headers)
    root_names = {f["name"] for f in root_listing.json()["data"]["folders"]}
    assert "Archive" not in root_names

    missing = client.get(f"/folders/{child_id}", headers=headers)
    assert missing.status_code == 404


def test_create_folder_treats_null_parent_as_root(client: TestClient) -> None:
    headers = _auth_header(client)

    omitted = client.post(
        "/folders",
        headers=headers,
        json={"name": "NoParent"},
    )
    assert omitted.status_code == 201, omitted.text
    assert omitted.json()["data"]["parent_id"] is None

    json_null = client.post(
        "/folders",
        headers=headers,
        json={"name": "JsonNull", "parent_folder_id": None},
    )
    assert json_null.status_code == 201, json_null.text
    assert json_null.json()["data"]["parent_id"] is None

    swagger_null = client.post(
        "/folders",
        headers=headers,
        json={"name": "SwaggerNull", "parent_folder_id": "null"},
    )
    assert swagger_null.status_code == 201, swagger_null.text
    assert swagger_null.json()["data"]["parent_id"] is None


def test_duplicate_folder_name_conflict(client: TestClient) -> None:
    headers = _auth_header(client)
    assert (
        client.post(
            "/folders",
            headers=headers,
            json={"name": "Photos"},
        ).status_code
        == 201
    )
    dup = client.post(
        "/folders",
        headers=headers,
        json={"name": "Photos"},
    )
    assert dup.status_code == 409


def test_cannot_move_folder_into_itself(client: TestClient) -> None:
    headers = _auth_header(client)
    created = client.post(
        "/folders",
        headers=headers,
        json={"name": "Loop"},
    )
    folder_id = created.json()["data"]["id"]
    response = client.post(
        f"/folders/{folder_id}/move",
        headers=headers,
        json={"destination_parent_folder_id": folder_id},
    )
    assert response.status_code == 400
