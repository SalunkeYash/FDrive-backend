from __future__ import annotations

import math
from uuid import UUID

from sqlalchemy.orm import Session

from dependencies import errors
from dependencies.config import settings
from integrations import s3 as s3_store
from integrations.sqs import enqueue_job
from models import File, FileObject, FileStatus, UploadSession, UploadSessionStatus, User
from uploads.schemas.uploads import (
    CompleteMultipartUploadRequest,
    GetPartUploadUrlResponse,
    InitiateMultipartUploadResponse,
)
from model_handler import file_model_handler as fq
from model_handler import folder_model_handler as folder_queries
from service import quota_service as quota


class MultipartUploadService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def initiate(
        self,
        owner: User,
        *,
        file_name: str,
        size_bytes: int,
        mime_type: str | None,
        folder_id: UUID | None,
        part_size_bytes: int,
    ) -> InitiateMultipartUploadResponse:
        try:
            file_name = fq.normalize_file_name(file_name)
        except ValueError as exc:
            raise errors.bad_request(str(exc)) from exc

        if folder_id is not None:
            folder = folder_queries.get_owned_folder(
                self.db, owner_id=owner.id, folder_id=folder_id
            )
            if folder is None:
                raise errors.not_found("Folder not found")

        quota.ensure_quota(owner, size_bytes)
        total_parts = max(1, math.ceil(size_bytes / part_size_bytes))

        file_row = File(
            owner_id=owner.id,
            folder_id=folder_id,
            name=file_name,
            mime_type=mime_type,
            size_bytes=size_bytes,
            status=FileStatus.pending,
        )
        self.db.add(file_row)
        self.db.flush()

        s3_key = s3_store.build_original_object_key(str(owner.id), str(file_row.id))
        upload_id = s3_store.initiate_multipart_upload(
            bucket=settings.s3_bucket,
            key=s3_key,
            content_type=mime_type,
        )
        self.db.add(
            FileObject(file_id=file_row.id, s3_bucket=settings.s3_bucket, s3_key=s3_key)
        )
        session = UploadSession(
            file_id=file_row.id,
            owner_id=owner.id,
            s3_upload_id=upload_id,
            status=UploadSessionStatus.uploading,
            parts_completed=0,
            total_parts=total_parts,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        return InitiateMultipartUploadResponse(
            file_id=file_row.id,
            upload_session_id=session.id,
            s3_upload_id=upload_id,
            s3_key=s3_key,
            part_size_bytes=part_size_bytes,
            total_parts=total_parts,
        )

    def get_part_upload_url(
        self, owner: User, upload_session_id: UUID, part_number: int
    ) -> GetPartUploadUrlResponse:
        session = self._require_session(owner, upload_session_id)
        file_row = fq.get_owned_file(self.db, owner_id=owner.id, file_id=session.file_id)
        if file_row is None or file_row.object is None or session.s3_upload_id is None:
            raise errors.bad_request("Upload session is invalid")

        url = s3_store.create_presigned_part_upload_url(
            bucket=file_row.object.s3_bucket,
            key=file_row.object.s3_key,
            upload_id=session.s3_upload_id,
            part_number=part_number,
        )
        return GetPartUploadUrlResponse(
            upload_url=url,
            part_number=part_number,
            expires_in_seconds=settings.s3_presign_expire_seconds,
        )

    def complete(
        self,
        owner: User,
        upload_session_id: UUID,
        body: CompleteMultipartUploadRequest,
    ) -> File:
        session = self._require_session(owner, upload_session_id)
        file_row = fq.get_owned_file(self.db, owner_id=owner.id, file_id=session.file_id)
        if file_row is None or file_row.object is None or session.s3_upload_id is None:
            raise errors.bad_request("Upload session is invalid")

        parts = [
            {"ETag": p.etag, "PartNumber": p.part_number}
            for p in sorted(body.parts, key=lambda x: x.part_number)
        ]
        s3_store.complete_multipart_upload(
            bucket=file_row.object.s3_bucket,
            key=file_row.object.s3_key,
            upload_id=session.s3_upload_id,
            parts=parts,
        )
        meta = s3_store.get_object_metadata(
            bucket=file_row.object.s3_bucket,
            key=file_row.object.s3_key,
        )
        stored_size = int(meta["ContentLength"])
        self.db.refresh(owner)
        quota.ensure_quota(owner, stored_size)
        file_row.size_bytes = stored_size
        file_row.status = FileStatus.ready
        file_row.object.etag = meta.get("ETag")
        session.status = UploadSessionStatus.completed
        session.parts_completed = len(parts)
        quota.add_bytes_used(owner, stored_size)
        self.db.commit()
        self.db.refresh(file_row)

        try:
            enqueue_job(
                "generate_thumbnail",
                {"file_id": str(file_row.id), "owner_id": str(owner.id)},
            )
        except Exception:
            pass

        return file_row

    def abort(self, owner: User, upload_session_id: UUID) -> None:
        session = self._require_session(owner, upload_session_id)
        file_row = fq.get_owned_file(self.db, owner_id=owner.id, file_id=session.file_id)
        if file_row is None or file_row.object is None or session.s3_upload_id is None:
            raise errors.bad_request("Upload session is invalid")
        if session.status == UploadSessionStatus.completed:
            raise errors.bad_request("Upload already completed")

        s3_store.abort_multipart_upload(
            bucket=file_row.object.s3_bucket,
            key=file_row.object.s3_key,
            upload_id=session.s3_upload_id,
        )
        session.status = UploadSessionStatus.aborted
        file_row.status = FileStatus.failed
        self.db.commit()

    def _require_session(self, owner: User, upload_session_id: UUID) -> UploadSession:
        from sqlalchemy import select

        session = self.db.scalar(
            select(UploadSession).where(
                UploadSession.id == upload_session_id,
                UploadSession.owner_id == owner.id,
            )
        )
        if session is None:
            raise errors.not_found("Upload session not found")
        return session
