from __future__ import annotations

from uuid import UUID

from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from app.core import errors
from app.core.config import settings
from app.integrations import s3 as s3_store
from app.models import File, FileObject, FileStatus, User
from app.schemas.files import FileResponse, RequestUploadUrlResponse
from app.services import file_queries as fq
from app.services import folder_queries, quota


class FileService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def request_upload_url(
        self,
        owner: User,
        *,
        file_name: str,
        size_bytes: int,
        mime_type: str | None,
        folder_id: UUID | None,
    ) -> RequestUploadUrlResponse:
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

        # Check quota before creating a pending file
        quota.ensure_quota(owner, size_bytes)

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
        self.db.add(
            FileObject(
                file_id=file_row.id,
                s3_bucket=settings.s3_bucket,
                s3_key=s3_key,
            )
        )
        self.db.commit()
        self.db.refresh(file_row)

        required_headers: dict[str, str] = {}
        if mime_type:
            required_headers["Content-Type"] = mime_type

        upload_url = s3_store.create_presigned_upload_url(
            bucket=settings.s3_bucket,
            key=s3_key,
            content_type=mime_type,
        )

        return RequestUploadUrlResponse(
            file_id=file_row.id,
            upload_url=upload_url,
            required_headers=required_headers,
            s3_key=s3_key,
            expires_in_seconds=settings.s3_presign_expire_seconds,
        )

    def complete_upload(self, owner: User, file_id: UUID) -> File:
        file_row = fq.get_owned_file(self.db, owner_id=owner.id, file_id=file_id)
        if file_row is None:
            raise errors.not_found("File not found")
        if file_row.status == FileStatus.ready:
            return file_row
        if file_row.status != FileStatus.pending:
            raise errors.bad_request("File is not waiting for upload")
        if file_row.object is None:
            raise errors.bad_request("File has no storage object")

        try:
            meta = s3_store.get_object_metadata(
                bucket=file_row.object.s3_bucket,
                key=file_row.object.s3_key,
            )
        except ClientError as exc:
            raise errors.bad_request(
                "Upload not found in storage yet. Upload the file, then complete again."
            ) from exc

        stored_size = int(meta["ContentLength"])
        if stored_size != file_row.size_bytes:
            file_row.status = FileStatus.failed
            self.db.commit()
            raise errors.bad_request(
                f"Uploaded size {stored_size} does not match declared size {file_row.size_bytes}"
            )

        # Re-check quota at complete time (usage may have changed)
        self.db.refresh(owner)
        quota.ensure_quota(owner, stored_size)

        file_row.status = FileStatus.ready
        file_row.object.etag = meta.get("ETag")
        if meta.get("ContentType"):
            file_row.mime_type = meta["ContentType"]
        quota.add_bytes_used(owner, stored_size)

        self.db.commit()
        self.db.refresh(file_row)
        return file_row

    def get_file(self, owner: User, file_id: UUID) -> File:
        file_row = fq.get_owned_file(self.db, owner_id=owner.id, file_id=file_id)
        if file_row is None:
            raise errors.not_found("File not found")
        return file_row

    def list_folder_files(
        self, owner: User, folder_id: UUID | None
    ) -> list[FileResponse]:
        if folder_id is not None:
            folder = folder_queries.get_owned_folder(
                self.db, owner_id=owner.id, folder_id=folder_id
            )
            if folder is None:
                raise errors.not_found("Folder not found")

        files = fq.list_files_in_folder(
            self.db, owner_id=owner.id, folder_id=folder_id
        )
        return [FileResponse.model_validate(f) for f in files]
