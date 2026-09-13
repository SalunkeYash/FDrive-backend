import io
import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from PIL import Image

from app.services.thumbnails import make_jpeg_thumbnail


def _register(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register-account",
        json={"email": email, "password": "securepass1", "display_name": "User"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _ready_image(client: TestClient, headers: dict[str, str]) -> str:
    with patch(
        "app.services.files.s3_store.create_presigned_upload_url",
        return_value="https://example.test/upload",
    ):
        requested = client.post(
            "/api/v1/files/request-upload-url",
            headers=headers,
            json={
                "file_name": "photo.png",
                "size_bytes": 12,
                "mime_type": "image/png",
            },
        )
    file_id = requested.json()["file_id"]
    with (
        patch(
            "app.services.files.s3_store.get_object_metadata",
            return_value={"ContentLength": 12, "ETag": '"i"', "ContentType": "image/png"},
        ),
        patch("app.services.files.enqueue_job", return_value="msg"),
    ):
        assert (
            client.post(
                f"/api/v1/files/{file_id}/complete-upload",
                headers=headers,
            ).status_code
            == 200
        )
    return file_id


def test_make_jpeg_thumbnail_shrinks_image() -> None:
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), color=(20, 40, 60)).save(buf, format="PNG")
    thumb = make_jpeg_thumbnail(buf.getvalue())
    assert thumb[:2] == b"\xff\xd8"  # JPEG magic
    with Image.open(io.BytesIO(thumb)) as out:
        assert max(out.size) <= 256


def test_make_jpeg_thumbnail_applies_exif_orientation() -> None:
    """Orientation 6 = rotate 90° CW for display; landscape pixels become portrait."""
    img = Image.new("RGB", (200, 100), color=(255, 0, 0))
    exif = img.getexif()
    exif[0x0112] = 6  # Orientation tag
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)

    thumb = make_jpeg_thumbnail(buf.getvalue())
    with Image.open(io.BytesIO(thumb)) as out:
        width, height = out.size
        assert height >= width
        assert max(out.size) <= 256


def test_request_preview_url_for_video(client: TestClient) -> None:
    headers = _register(client, f"vid-{uuid.uuid4().hex[:8]}@example.com")
    with patch(
        "app.services.files.s3_store.create_presigned_upload_url",
        return_value="https://example.test/upload",
    ):
        requested = client.post(
            "/api/v1/files/request-upload-url",
            headers=headers,
            json={
                "file_name": "clip.mp4",
                "size_bytes": 20,
                "mime_type": "video/mp4",
            },
        )
    file_id = requested.json()["file_id"]
    with (
        patch(
            "app.services.files.s3_store.get_object_metadata",
            return_value={"ContentLength": 20, "ETag": '"v"', "ContentType": "video/mp4"},
        ),
        patch("app.services.files.enqueue_job", return_value="msg"),
    ):
        assert (
            client.post(
                f"/api/v1/files/{file_id}/complete-upload",
                headers=headers,
            ).status_code
            == 200
        )

    with (
        patch("app.services.previews.s3_store.get_object_metadata", return_value={}),
        patch(
            "app.services.previews.s3_store.create_presigned_download_url",
            return_value="https://example.test/video-preview",
        ) as presign,
    ):
        response = client.get(
            f"/api/v1/previews/{file_id}/request-preview-url",
            headers=headers,
        )
    assert response.status_code == 200, response.text
    assert response.json()["mime_type"] == "video/mp4"
    assert presign.call_args.kwargs.get("inline") is True

    headers = _register(client, f"prev-{uuid.uuid4().hex[:8]}@example.com")
    file_id = _ready_image(client, headers)

    with (
        patch("app.services.previews.s3_store.get_object_metadata", return_value={}),
        patch(
            "app.services.previews.s3_store.create_presigned_download_url",
            return_value="https://example.test/preview",
        ) as presign,
    ):
        response = client.get(
            f"/api/v1/previews/{file_id}/request-preview-url",
            headers=headers,
        )
    assert response.status_code == 200, response.text
    assert response.json()["preview_url"] == "https://example.test/preview"
    assert response.json()["variant"] == "preview"
    assert presign.call_args.kwargs.get("inline") is True


def test_request_thumbnail_url_when_ready(client: TestClient) -> None:
    headers = _register(client, f"thumb-{uuid.uuid4().hex[:8]}@example.com")
    file_id = _ready_image(client, headers)

    with (
        patch("app.services.previews.s3_store.object_exists", return_value=True),
        patch(
            "app.services.previews.s3_store.create_presigned_download_url",
            return_value="https://example.test/thumb",
        ),
    ):
        response = client.get(
            f"/api/v1/previews/{file_id}/request-thumbnail-url",
            headers=headers,
        )
    assert response.status_code == 200, response.text
    assert response.json()["variant"] == "thumbnail"
    assert response.json()["mime_type"] == "image/jpeg"


def test_request_thumbnail_url_queues_when_missing(client: TestClient) -> None:
    headers = _register(client, f"miss-{uuid.uuid4().hex[:8]}@example.com")
    file_id = _ready_image(client, headers)

    with (
        patch("app.services.previews.s3_store.object_exists", return_value=False),
        patch("app.services.previews.enqueue_job", return_value="queued") as enqueue,
        patch(
            "app.services.thumbnails.generate_thumbnail_for_file",
            return_value=False,
        ),
    ):
        response = client.get(
            f"/api/v1/previews/{file_id}/request-thumbnail-url",
            headers=headers,
        )
    assert response.status_code == 404
    enqueue.assert_called_once()


def test_generate_thumbnail_for_file_uploads(monkeypatch) -> None:
    from uuid import uuid4

    from app.services import thumbnails as thumb_mod

    file_id = uuid4()
    owner_id = uuid4()
    fake_file = MagicMock()
    fake_file.id = file_id
    fake_file.owner_id = owner_id
    fake_file.status = MagicMock()
    from app.models import FileStatus

    fake_file.status = FileStatus.ready
    fake_file.is_trashed = False
    fake_file.mime_type = "image/png"
    fake_file.object = MagicMock(s3_bucket="fdrive", s3_key="users/x/files/y/original")

    buf = io.BytesIO()
    Image.new("RGB", (100, 80), color=(1, 2, 3)).save(buf, format="PNG")

    db = MagicMock()
    db.scalar.return_value = fake_file

    with (
        patch.object(thumb_mod.s3_store, "download_object_bytes", return_value=buf.getvalue()),
        patch.object(thumb_mod.s3_store, "upload_object_bytes") as upload,
    ):
        assert thumb_mod.generate_thumbnail_for_file(db, file_id) is True
    upload.assert_called_once()
    assert "previews/thumb" in upload.call_args.kwargs["key"]
