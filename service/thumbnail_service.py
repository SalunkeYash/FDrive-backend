"""Image, RAW, and video thumbnail generation."""

from __future__ import annotations

import io
import logging
import tempfile
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from integrations import s3 as s3_store
from models import File, FileStatus

logger = logging.getLogger("fdrive.thumbnails")

THUMB_VARIANT = "thumb_v2"
THUMB_MAX_SIZE = (256, 256)
# Larger JPEG used when opening RAW in the media viewer (browsers can't show RAW).
PREVIEW_VARIANT = "preview_v1"
PREVIEW_MAX_SIZE = (1600, 1600)
IMAGE_MIME_PREFIXES = ("image/",)
VIDEO_MIME_PREFIXES = ("video/",)

# Camera RAW — browsers can't display these; we extract an embedded JPEG or demosaic.
RAW_EXTENSIONS = frozenset(
    {
        "raw",
        "cr2",
        "cr3",
        "nef",
        "nrw",
        "arw",
        "srf",
        "sr2",
        "dng",
        "orf",
        "rw2",
        "pef",
        "ptx",
        "srw",
        "raf",
        "x3f",
        "3fr",
        "erf",
        "kdc",
        "dcr",
        "mrw",
        "rwl",
        "iiq",
        "bay",
        "cap",
        "data",
        "dcs",
        "drf",
        "eip",
        "fff",
        "mef",
        "mos",
        "rwz",
    }
)

RAW_MIME_HINTS = (
    "image/x-adobe-dng",
    "image/x-canon-cr2",
    "image/x-canon-cr3",
    "image/x-canon-crw",
    "image/x-nikon-nef",
    "image/x-nikon-nrw",
    "image/x-sony-arw",
    "image/x-sony-sr2",
    "image/x-sony-srf",
    "image/x-panasonic-rw2",
    "image/x-olympus-orf",
    "image/x-fuji-raf",
    "image/x-pentax-pef",
    "image/x-samsung-srw",
    "image/x-sigma-x3f",
    "image/x-raw",
    "image/x-dcraw",
    "image/raw",
)


def extension_of(name: str | None) -> str:
    if not name or "." not in name:
        return ""
    return name.rsplit(".", 1)[-1].lower()


def is_raw_mime(mime_type: str | None) -> bool:
    if not mime_type:
        return False
    lowered = mime_type.lower().strip()
    if lowered in RAW_MIME_HINTS:
        return True
    if "raw" in lowered and lowered.startswith("image/"):
        return True
    return False


def is_raw_file(mime_type: str | None, file_name: str | None = None) -> bool:
    if is_raw_mime(mime_type):
        return True
    return extension_of(file_name) in RAW_EXTENSIONS


def is_image_mime(mime_type: str | None) -> bool:
    if not mime_type:
        return False
    lowered = mime_type.lower()
    if not lowered.startswith(IMAGE_MIME_PREFIXES):
        return False
    # RAW is image/* on some clients but needs a different decoder.
    if is_raw_mime(mime_type):
        return False
    return True


def is_video_mime(mime_type: str | None) -> bool:
    if not mime_type:
        return False
    return mime_type.lower().startswith(VIDEO_MIME_PREFIXES)


def is_media_mime(mime_type: str | None, file_name: str | None = None) -> bool:
    return (
        is_image_mime(mime_type)
        or is_video_mime(mime_type)
        or is_raw_file(mime_type, file_name)
    )


def make_jpeg_thumbnail(image_bytes: bytes, max_size: tuple[int, int] = THUMB_MAX_SIZE) -> bytes:
    """Shrink an image to a JPEG thumb, honoring EXIF orientation from cameras/phones."""
    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(image_bytes)) as img:
        img = ImageOps.exif_transpose(img) or img
        img = img.convert("RGB")
        img.thumbnail(max_size)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85, optimize=True)
        return out.getvalue()


def make_raw_jpeg_thumbnail(
    raw_bytes: bytes, max_size: tuple[int, int] = THUMB_MAX_SIZE
) -> bytes:
    """
    Build a JPEG thumb from a camera RAW file.

    Prefer the embedded JPEG preview (fast). Fall back to a half-size demosaic
    when no usable embedded thumb exists.
    """
    import numpy as np
    import rawpy
    from PIL import Image

    with rawpy.imread(io.BytesIO(raw_bytes)) as raw:
        try:
            thumb = raw.extract_thumb()
        except rawpy.LibRawNoThumbnailError:
            thumb = None
        except rawpy.LibRawError:
            thumb = None

        if thumb is not None:
            if thumb.format == rawpy.ThumbFormat.JPEG:
                return make_jpeg_thumbnail(thumb.data, max_size=max_size)
            if thumb.format == rawpy.ThumbFormat.BITMAP:
                # Bitmap thumbnails are typically RGB arrays.
                arr = np.asarray(thumb.data)
                img = Image.fromarray(arr)
                img = img.convert("RGB")
                img.thumbnail(max_size)
                out = io.BytesIO()
                img.save(out, format="JPEG", quality=85, optimize=True)
                return out.getvalue()

        # Full demosaic is heavier — half_size keeps thumbnail generation practical.
        rgb = raw.postprocess(
            use_camera_wb=True,
            half_size=True,
            no_auto_bright=False,
            output_bps=8,
        )
        img = Image.fromarray(rgb)
        img.thumbnail(max_size)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85, optimize=True)
        return out.getvalue()


def make_raw_jpeg_preview(
    raw_bytes: bytes, max_size: tuple[int, int] = PREVIEW_MAX_SIZE
) -> bytes:
    """Larger JPEG for the in-app viewer (still much smaller than full demosaic)."""
    return make_raw_jpeg_thumbnail(raw_bytes, max_size=max_size)


def ensure_raw_preview_jpeg(db: Session, file_id: UUID) -> str | None:
    """
    Ensure a large JPEG preview exists in S3 for a RAW file.
    Returns the S3 key, or None if generation failed / not RAW.
    """
    file_row = db.scalar(
        select(File).where(File.id == file_id).options(joinedload(File.object))
    )
    if file_row is None or file_row.object is None:
        return None
    if not is_raw_file(file_row.mime_type, file_row.name):
        return None

    preview_key = s3_store.build_preview_object_key(
        str(file_row.owner_id),
        str(file_row.id),
        PREVIEW_VARIANT,
    )
    if s3_store.object_exists(bucket=file_row.object.s3_bucket, key=preview_key):
        return preview_key

    original = s3_store.download_object_bytes(
        bucket=file_row.object.s3_bucket,
        key=file_row.object.s3_key,
    )
    try:
        preview_bytes = make_raw_jpeg_preview(original)
    except Exception:
        logger.exception("RAW preview generation failed file_id=%s", file_id)
        return None

    s3_store.upload_object_bytes(
        bucket=file_row.object.s3_bucket,
        key=preview_key,
        body=preview_bytes,
        content_type="image/jpeg",
    )
    logger.info("RAW preview written file_id=%s key=%s", file_id, preview_key)
    return preview_key


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
    Supports images (Pillow), camera RAW (rawpy), and videos (PyAV).
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
        if is_raw_file(file_row.mime_type, file_row.name):
            thumb_bytes = make_raw_jpeg_thumbnail(original)
        elif is_image_mime(file_row.mime_type):
            thumb_bytes = make_jpeg_thumbnail(original)
        elif is_video_mime(file_row.mime_type):
            thumb_bytes = make_video_jpeg_thumbnail(original)
        else:
            logger.info(
                "thumbnail skipped: unsupported mime file_id=%s mime=%s name=%s",
                file_id,
                file_row.mime_type,
                file_row.name,
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
