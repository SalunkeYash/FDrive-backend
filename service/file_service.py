from __future__ import annotations

from uuid import UUID

from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from dependencies import errors
from dependencies.config import settings
from integrations import s3 as s3_store
from integrations.sqs import enqueue_job
from models import File, FileObject, FileStatus, User
from files.schemas.files import (
    FileResponse,
    RequestDownloadUrlResponse,
    RequestUploadUrlResponse,
)
from model_handler import file_model_handler as fq
from model_handler import folder_model_handler as folder_queries
from service import permission_service as permissions
from service import quota_service as quota
from model_handler.user_model_handler import get_user_by_id


def _file_response(db: Session, user: User, file_row: File) -> FileResponse:
    data = FileResponse.model_validate(file_row)
    return data.model_copy(update={"access_role": permissions.role_for_file(db, user, file_row)})


class FileService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def request_upload_url(
        self,
        user: User,
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

        drive_owner = user
        if folder_id is not None:
            folder = permissions.require_edit_folder(self.db, user, folder_id)
            if folder.owner_id != user.id:
                owner = get_user_by_id(self.db, folder.owner_id)
                if owner is None:
                    raise errors.not_found("Folder owner not found")
                drive_owner = owner

        # Check quota against the drive that will own the file
        quota.ensure_quota(drive_owner, size_bytes)

        file_row = File(
            owner_id=drive_owner.id,
            folder_id=folder_id,
            name=file_name,
            mime_type=mime_type,
            size_bytes=size_bytes,
            status=FileStatus.pending,
        )
        self.db.add(file_row)
        self.db.flush()

        s3_key = s3_store.build_original_object_key(str(drive_owner.id), str(file_row.id))
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

    def complete_upload(self, user: User, file_id: UUID) -> File:
        file_row = fq.get_file_by_id(self.db, file_id, include_trashed=True)
        if file_row is None:
            raise errors.not_found("File not found")

        can_complete = file_row.owner_id == user.id
        if not can_complete and file_row.folder_id is not None:
            folder = folder_queries.get_folder_by_id(self.db, file_row.folder_id)
            can_complete = folder is not None and permissions.can_edit_folder(
                self.db, user, folder
            )
        if not can_complete:
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

        drive_owner = get_user_by_id(self.db, file_row.owner_id)
        if drive_owner is None:
            raise errors.not_found("File owner not found")
        self.db.refresh(drive_owner)
        quota.ensure_quota(drive_owner, stored_size)

        file_row.status = FileStatus.ready
        file_row.object.etag = meta.get("ETag")
        if meta.get("ContentType"):
            file_row.mime_type = meta["ContentType"]
        quota.add_bytes_used(drive_owner, stored_size)

        self.db.commit()
        self.db.refresh(file_row)

        try:
            enqueue_job(
                "generate_thumbnail",
                {"file_id": str(file_row.id), "owner_id": str(drive_owner.id)},
            )
        except Exception:
            pass

        return file_row

    def get_file(self, user: User, file_id: UUID) -> File:
        return permissions.require_view_file(self.db, user, file_id)

    def get_file_response(self, user: User, file_id: UUID) -> FileResponse:
        file_row = self.get_file(user, file_id)
        return _file_response(self.db, user, file_row)

    def request_download_url(self, user: User, file_id: UUID) -> RequestDownloadUrlResponse:
        file_row = self.get_file(user, file_id)
        if file_row.status != FileStatus.ready:
            raise errors.bad_request("File is not ready to download")
        if file_row.object is None:
            raise errors.bad_request("File has no storage object")

        download_url = s3_store.create_presigned_download_url(
            bucket=file_row.object.s3_bucket,
            key=file_row.object.s3_key,
            download_filename=file_row.name,
            content_type=file_row.mime_type,
        )
        return RequestDownloadUrlResponse(
            file_id=file_row.id,
            file_name=file_row.name,
            download_url=download_url,
            expires_in_seconds=settings.s3_presign_expire_seconds,
            size_bytes=file_row.size_bytes,
            mime_type=file_row.mime_type,
        )

    def list_folder_files(
        self, user: User, folder_id: UUID | None
    ) -> list[FileResponse]:
        if folder_id is not None:
            folder = permissions.require_view_folder(self.db, user, folder_id)
            drive_owner_id = folder.owner_id
        else:
            drive_owner_id = user.id

        files = fq.list_files_in_folder(
            self.db, owner_id=drive_owner_id, folder_id=folder_id
        )
        # Root listing is always the caller's own root (not shared roots).
        if folder_id is None:
            return [_file_response(self.db, user, f) for f in files]

        # Shared folder: only return files the user can view (normally all via inheritance).
        return [
            _file_response(self.db, user, f)
            for f in files
            if permissions.can_view_file(self.db, user, f)
        ]

    def rename_file(self, user: User, file_id: UUID, file_name: str) -> File:
        try:
            file_name = fq.normalize_file_name(file_name)
        except ValueError as exc:
            raise errors.bad_request(str(exc)) from exc

        file_row = self._require_ready_editable_file(user, file_id)
        file_row.name = file_name
        self.db.commit()
        self.db.refresh(file_row)
        return file_row

    def move_file(
        self,
        user: User,
        file_id: UUID,
        destination_folder_id: UUID | None,
    ) -> File:
        file_row = self._require_ready_editable_file(user, file_id)
        self._require_editable_destination(user, file_row.owner_id, destination_folder_id)
        file_row.folder_id = destination_folder_id
        self.db.commit()
        self.db.refresh(file_row)
        return file_row

    def copy_file(
        self,
        user: User,
        file_id: UUID,
        *,
        destination_folder_id: UUID | None,
        new_file_name: str | None,
    ) -> File:
        # Copy always lands in the caller's drive (or a folder they can edit that they own).
        source = permissions.require_view_file(self.db, user, file_id)
        if source.status != FileStatus.ready:
            raise errors.bad_request("File is not ready")
        if source.object is None:
            raise errors.bad_request("File has no storage object")

        drive_owner = user
        if destination_folder_id is not None:
            dest = permissions.require_edit_folder(self.db, user, destination_folder_id)
            if dest.owner_id != user.id:
                raise errors.forbidden("Can only copy into your own folders")
        else:
            # root of caller's drive
            pass

        name = new_file_name if new_file_name is not None else source.name
        try:
            name = fq.normalize_file_name(name)
        except ValueError as exc:
            raise errors.bad_request(str(exc)) from exc

        self.db.refresh(drive_owner)
        quota.ensure_quota(drive_owner, source.size_bytes)

        copy_row = File(
            owner_id=drive_owner.id,
            folder_id=destination_folder_id,
            name=name,
            mime_type=source.mime_type,
            size_bytes=source.size_bytes,
            status=FileStatus.ready,
        )
        self.db.add(copy_row)
        self.db.flush()

        new_key = s3_store.build_original_object_key(str(drive_owner.id), str(copy_row.id))
        try:
            s3_store.copy_object(
                source_bucket=source.object.s3_bucket,
                source_key=source.object.s3_key,
                destination_bucket=settings.s3_bucket,
                destination_key=new_key,
            )
        except ClientError as exc:
            self.db.rollback()
            raise errors.bad_request("Could not copy file in storage") from exc

        self.db.add(
            FileObject(
                file_id=copy_row.id,
                s3_bucket=settings.s3_bucket,
                s3_key=new_key,
                etag=source.object.etag,
            )
        )
        quota.add_bytes_used(drive_owner, source.size_bytes)
        self.db.commit()
        self.db.refresh(copy_row)
        return copy_row

    def _require_ready_editable_file(self, user: User, file_id: UUID) -> File:
        file_row = permissions.require_edit_file(self.db, user, file_id)
        if file_row.status != FileStatus.ready:
            raise errors.bad_request("File is not ready")
        return file_row

    def _require_editable_destination(
        self, user: User, drive_owner_id: UUID, destination_folder_id: UUID | None
    ) -> None:
        if destination_folder_id is None:
            # Moving to root is only allowed for the drive owner.
            if user.id != drive_owner_id:
                raise errors.forbidden("Editors cannot move items to another user's root")
            return
        folder = permissions.require_edit_folder(self.db, user, destination_folder_id)
        if folder.owner_id != drive_owner_id:
            raise errors.bad_request("Destination must stay in the same drive")
