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
from app.services import file_queries as fq
from app.services.thumbnails import THUMB_VARIANT, is_image_mime


class PreviewService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def request_thumbnail_url(self, owner: User, file_id: UUID) -> PreviewUrlResponse:
        file_row = self._require_ready_file(owner, file_id)
        if not is_image_mime(file_row.mime_type):
            raise errors.bad_request("Thumbnails are only available for images")

        thumb_key = s3_store.build_preview_object_key(
            str(owner.id), str(file_row.id), THUMB_VARIANT
        )
        if not s3_store.object_exists(bucket=file_row.object.s3_bucket, key=thumb_key):
            try:
                enqueue_job(
                    "generate_thumbnail",
                    {"file_id": str(file_row.id), "owner_id": str(owner.id)},
                )
            except Exception:
                pass
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

    def request_preview_url(self, owner: User, file_id: UUID) -> PreviewUrlResponse:
        """Inline preview of the original for images (browser display, not download)."""
        file_row = self._require_ready_file(owner, file_id)
        if not is_image_mime(file_row.mime_type):
            raise errors.bad_request("Inline preview is only available for images")

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

    def _require_ready_file(self, owner: User, file_id: UUID):
        file_row = fq.get_owned_file(self.db, owner_id=owner.id, file_id=file_id)
        if file_row is None:
            raise errors.not_found("File not found")
        if file_row.status != FileStatus.ready:
            raise errors.bad_request("File is not ready")
        if file_row.object is None:
            raise errors.bad_request("File has no storage object")
        return file_row
