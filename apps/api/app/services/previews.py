from __future__ import annotations

from uuid import UUID

from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from app.core import errors
from app.core.config import settings
from app.integrations import s3 as s3_store
from app.integrations.sqs import enqueue_job
from app.models import FileStatus, User
from app.schemas.previews import PreviewUrlResponse
from app.services.thumbnails import (
    THUMB_VARIANT,
    ensure_raw_preview_jpeg,
    is_media_mime,
    is_raw_file,
)


class PreviewService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def request_thumbnail_url(self, owner: User, file_id: UUID) -> PreviewUrlResponse:
        file_row = self._require_ready_file(owner, file_id)
        if not is_media_mime(file_row.mime_type, file_row.name):
            raise errors.bad_request(
                "Thumbnails are only available for images, RAW photos, and videos"
            )

        return self._jpeg_thumb_response(file_row)

    def request_preview_url(self, owner: User, file_id: UUID) -> PreviewUrlResponse:
        """Inline preview for browser display (JPEG for RAW; original for images/videos)."""
        file_row = self._require_ready_file(owner, file_id)
        if not is_media_mime(file_row.mime_type, file_row.name):
            raise errors.bad_request(
                "Inline preview is only available for images, RAW photos, and videos"
            )

        # Browsers cannot render camera RAW — serve a large JPEG preview instead.
        if is_raw_file(file_row.mime_type, file_row.name):
            preview_key = ensure_raw_preview_jpeg(self.db, file_row.id)
            if preview_key is None:
                # Fall back to grid thumb if large preview cannot be built.
                return self._jpeg_thumb_response(file_row)
            url = s3_store.create_presigned_download_url(
                bucket=file_row.object.s3_bucket,
                key=preview_key,
                download_filename=f"{file_row.name}.preview.jpg",
                content_type="image/jpeg",
                inline=True,
            )
            return PreviewUrlResponse(
                file_id=file_row.id,
                variant="preview",
                preview_url=url,
                expires_in_seconds=settings.s3_presign_expire_seconds,
                mime_type="image/jpeg",
            )

        try:
            s3_store.get_object_metadata(
                bucket=file_row.object.s3_bucket,
                key=file_row.object.s3_key,
            )
        except ClientError as exc:
            raise errors.not_found("Original object missing in storage") from exc

        url = s3_store.create_presigned_download_url(
            bucket=file_row.object.s3_bucket,
            key=file_row.object.s3_key,
            download_filename=file_row.name,
            content_type=file_row.mime_type,
            inline=True,
        )
        return PreviewUrlResponse(
            file_id=file_row.id,
            variant="preview",
            preview_url=url,
            expires_in_seconds=settings.s3_presign_expire_seconds,
            mime_type=file_row.mime_type,
        )

    def _jpeg_thumb_response(self, file_row) -> PreviewUrlResponse:
        thumb_key = s3_store.build_preview_object_key(
            str(file_row.owner_id), str(file_row.id), THUMB_VARIANT
        )
        if not s3_store.object_exists(bucket=file_row.object.s3_bucket, key=thumb_key):
            try:
                enqueue_job(
                    "generate_thumbnail",
                    {"file_id": str(file_row.id), "owner_id": str(file_row.owner_id)},
                )
            except Exception:
                pass

            from app.services.thumbnails import generate_thumbnail_for_file

            generated = generate_thumbnail_for_file(self.db, file_row.id)
            if not generated or not s3_store.object_exists(
                bucket=file_row.object.s3_bucket, key=thumb_key
            ):
                raise errors.not_found(
                    "Thumbnail is not ready yet. A generation job was queued; try again shortly."
                )

        url = s3_store.create_presigned_download_url(
            bucket=file_row.object.s3_bucket,
            key=thumb_key,
            download_filename=f"{file_row.name}.thumb.jpg",
            content_type="image/jpeg",
            inline=True,
        )
        return PreviewUrlResponse(
            file_id=file_row.id,
            variant="thumbnail",
            preview_url=url,
            expires_in_seconds=settings.s3_presign_expire_seconds,
            mime_type="image/jpeg",
        )

    def _require_ready_file(self, user: User, file_id: UUID):
        from app.services import permissions

        file_row = permissions.require_view_file(self.db, user, file_id)
        if file_row.status != FileStatus.ready:
            raise errors.bad_request("File is not ready")
        if file_row.object is None:
            raise errors.bad_request("File has no storage object")
        return file_row
