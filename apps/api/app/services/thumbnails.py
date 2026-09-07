"""Image and video thumbnail generation."""

from __future__ import annotations

import io
import logging
import tempfile
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.integrations import s3 as s3_store
from app.models import File, FileStatus

logger = logging.getLogger("fdrive.thumbnails")

THUMB_VARIANT = "thumb"
THUMB_MAX_SIZE = (256, 256)
IMAGE_MIME_PREFIXES = ("image/",)
VIDEO_MIME_PREFIXES = ("video/",)


def is_image_mime(mime_type: str | None) -> bool:
    if not mime_type:
        return False
    return mime_type.lower().startswith(IMAGE_MIME_PREFIXES)


def is_video_mime(mime_type: str | None) -> bool:
    if not mime_type:
        return False
    return mime_type.lower().startswith(VIDEO_MIME_PREFIXES)


def is_media_mime(mime_type: str | None) -> bool:
    return is_image_mime(mime_type) or is_video_mime(mime_type)


def make_jpeg_thumbnail(image_bytes: bytes, max_size: tuple[int, int] = THUMB_MAX_SIZE) -> bytes:
    from PIL import Image

    with Image.open(io.BytesIO(image_bytes)) as img:
        img = img.convert("RGB")
        img.thumbnail(max_size)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85, optimize=True)
        return out.getvalue()


def make_video_jpeg_thumbnail(
    video_bytes: bytes, max_size: tuple[int, int] = THUMB_MAX_SIZE
) -> bytes:
    """Grab an early frame with PyAV and shrink to a JPEG thumb."""
    import av
    from PIL import Image

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(video_bytes)
        tmp_path = Path(tmp.name)

    try:
        container = av.open(str(tmp_path))
        frame_image: Image.Image | None = None
        try:
            for frame in container.decode(video=0):
                frame_image = frame.to_image()
                break
        finally:
            container.close()

        if frame_image is None:
            raise ValueError("No video frame available for thumbnail")

        frame_image = frame_image.convert("RGB")
        frame_image.thumbnail(max_size)
        out = io.BytesIO()
        frame_image.save(out, format="JPEG", quality=85, optimize=True)
        return out.getvalue()
    finally:
        tmp_path.unlink(missing_ok=True)


def generate_thumbnail_for_file(db: Session, file_id: UUID) -> bool:
    """
    Download original, write previews/thumb to S3.
    Supports images (Pillow) and videos (PyAV frame grab).
    Returns True if a thumbnail was written, False if skipped.
    """
    file_row = db.scalar(
        select(File).where(File.id == file_id).options(joinedload(File.object))
    )
    if file_row is None or file_row.object is None:
        logger.warning("thumbnail skipped: file missing file_id=%s", file_id)
        return False
    if file_row.status != FileStatus.ready or file_row.is_trashed:
        logger.info("thumbnail skipped: file not ready file_id=%s", file_id)
        return False

    original = s3_store.download_object_bytes(
        bucket=file_row.object.s3_bucket,
        key=file_row.object.s3_key,
    )

    try:
        if is_image_mime(file_row.mime_type):
            thumb_bytes = make_jpeg_thumbnail(original)
        elif is_video_mime(file_row.mime_type):
            thumb_bytes = make_video_jpeg_thumbnail(original)
        else:
            logger.info(
                "thumbnail skipped: unsupported mime file_id=%s mime=%s",
                file_id,
                file_row.mime_type,
            )
            return False
    except Exception:
        logger.exception("thumbnail generation failed file_id=%s", file_id)
        return False

    thumb_key = s3_store.build_preview_object_key(
        str(file_row.owner_id),
        str(file_row.id),
        THUMB_VARIANT,
    )
    s3_store.upload_object_bytes(
        bucket=file_row.object.s3_bucket,
        key=thumb_key,
        body=thumb_bytes,
        content_type="image/jpeg",
    )
    logger.info("thumbnail written file_id=%s key=%s", file_id, thumb_key)
    return True
