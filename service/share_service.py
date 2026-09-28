from __future__ import annotations

import secrets
from uuid import UUID

from botocore.exceptions import ClientError
from sqlalchemy import select
from sqlalchemy.orm import Session

from dependencies import errors
from dependencies.config import settings
from integrations import s3 as s3_store
from models import AccessRequest, AccessRequestStatus, File, FileStatus, Folder, Share, ShareRole, User
from files.schemas.files import FileResponse, RequestDownloadUrlResponse
from folders.schemas.folders import FolderResponse
from previews.schemas.previews import PreviewUrlResponse
from shares.schemas.shares import (
    AccessRequestResponse,
    ResourceAccessPerson,
    ResourceAccessResponse,
    ResourceLinkAccess,
    ResolveSharedItemResponse,
    SharedLinkAccessResponse,
    SharedLinkContentsResponse,
    ShareResponse,
    SharedWithMeItem,
)
from model_handler import file_model_handler as file_queries
from model_handler import folder_model_handler as folder_queries
from service import permission_service as permissions
from service.thumbnail_service import (
    THUMB_VARIANT,
    ensure_raw_preview_jpeg,
    is_media_mime,
    is_raw_file,
)
from model_handler.user_model_handler import get_user_by_email, get_user_by_id


def _role_value(role: ShareRole | str) -> str:
    return role.value if hasattr(role, "value") else str(role)


class ShareService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_user_share(
        self,
        owner: User,
        *,
        resource_type: str,
        resource_id: UUID,
        grantee_email: str,
        role: str,
    ) -> Share:
        self._require_owned_resource(owner, resource_type, resource_id)
        grantee = get_user_by_email(self.db, grantee_email)
        if grantee is None:
            raise errors.not_found("Grantee user not found")
        if grantee.id == owner.id:
            raise errors.bad_request("Cannot share with yourself")

        existing = permissions.get_share_for_user(
            self.db,
            user_id=grantee.id,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        if existing is not None:
            existing.role = ShareRole(role)
            self.db.commit()
            self.db.refresh(existing)
            return existing

        share = Share(
            owner_id=owner.id,
            resource_type=resource_type,
            resource_id=resource_id,
            grantee_user_id=grantee.id,
            role=ShareRole(role),
            token=None,
        )
        self.db.add(share)
        self.db.commit()
        self.db.refresh(share)
        return share

    def create_link_share(
        self,
        owner: User,
        *,
        resource_type: str,
        resource_id: UUID,
        role: str,
    ) -> Share:
        """Enable anyone-with-the-link access (upsert one link share per resource)."""
        share = self.set_link_access(
            owner,
            resource_type=resource_type,
            resource_id=resource_id,
            access="anyone",
            role=role,
        )
        assert share is not None
        return share

    def set_link_access(
        self,
        owner: User,
        *,
        resource_type: str,
        resource_id: UUID,
        access: str,
        role: str,
    ) -> Share | None:
        self._require_owned_resource(owner, resource_type, resource_id)
        existing = permissions.get_link_share_for_resource(
            self.db, resource_type=resource_type, resource_id=resource_id
        )

        if access == "restricted":
            if existing is not None:
                self.db.delete(existing)
                self.db.commit()
            return None

        if existing is not None:
            existing.role = ShareRole(role)
            if not existing.token:
                existing.token = secrets.token_urlsafe(24)
            self.db.commit()
            self.db.refresh(existing)
            return existing

        share = Share(
            owner_id=owner.id,
            resource_type=resource_type,
            resource_id=resource_id,
            grantee_user_id=None,
            role=ShareRole(role),
            token=secrets.token_urlsafe(24),
        )
        self.db.add(share)
        self.db.commit()
        self.db.refresh(share)
        return share

    def get_resource_access(
        self,
        owner: User,
        *,
        resource_type: str,
        resource_id: UUID,
    ) -> ResourceAccessResponse:
        self._require_owned_resource(owner, resource_type, resource_id)
        people: list[ResourceAccessPerson] = []
        for share in permissions.list_user_shares_for_resource(
            self.db,
            owner_id=owner.id,
            resource_type=resource_type,
            resource_id=resource_id,
        ):
            if share.grantee_user_id is None:
                continue
            grantee = get_user_by_id(self.db, share.grantee_user_id)
            if grantee is None:
                continue
            people.append(
                ResourceAccessPerson(
                    share_id=share.id,
                    email=grantee.email,
                    display_name=grantee.display_name,
                    role=_role_value(share.role),
                )
            )

        link_share = permissions.get_link_share_for_resource(
            self.db, resource_type=resource_type, resource_id=resource_id
        )
        link = (
            ResourceLinkAccess(
                enabled=True,
                share_id=link_share.id,
                token=link_share.token,
                role=_role_value(link_share.role),
            )
            if link_share is not None
            else ResourceLinkAccess(enabled=False)
        )

        return ResourceAccessResponse(
            resource_type=resource_type,
            resource_id=resource_id,
            owner=ResourceAccessPerson(
                email=owner.email,
                display_name=owner.display_name,
                role="owner",
            ),
            people=people,
            link=link,
        )

    def list_my_shares(self, owner: User) -> list[ShareResponse]:
        shares = permissions.list_shares_for_owner(self.db, owner.id)
        return [ShareResponse.model_validate(s) for s in shares]

    def list_shared_with_me(self, user: User) -> list[SharedWithMeItem]:
        shares = permissions.list_shares_with_me(self.db, user.id)
        items: list[SharedWithMeItem] = []
        for share in shares:
            role = _role_value(share.role)
            if share.resource_type == "file":
                file_row = file_queries.get_file_by_id(
                    self.db, share.resource_id, include_trashed=True
                )
                if file_row is None:
                    continue
                items.append(
                    SharedWithMeItem(
                        share_id=share.id,
                        resource_type="file",
                        resource_id=file_row.id,
                        role=role,
                        resource_name=file_row.name,
                        mime_type=file_row.mime_type,
                        size_bytes=file_row.size_bytes,
                        folder_id=file_row.folder_id,
                        updated_at=file_row.updated_at,
                        is_trashed=file_row.is_trashed,
                    )
                )
            else:
                folder = self.db.scalar(select(Folder).where(Folder.id == share.resource_id))
                if folder is None:
                    continue
                items.append(
                    SharedWithMeItem(
                        share_id=share.id,
                        resource_type="folder",
                        resource_id=folder.id,
                        role=role,
                        resource_name=folder.name,
                        parent_id=folder.parent_id,
                        updated_at=folder.updated_at,
                        is_trashed=folder.is_trashed,
                    )
                )
        return items

    def revoke_share(self, owner: User, share_id: UUID) -> None:
        share = self.db.scalar(
            select(Share).where(Share.id == share_id, Share.owner_id == owner.id)
        )
        if share is None:
            raise errors.not_found("Share not found")
        self.db.delete(share)
        self.db.commit()

    def access_shared_link(self, token: str) -> SharedLinkAccessResponse:
        share = permissions.get_share_by_token(self.db, token)
        if share is None:
            raise errors.not_found("Share link not found or expired")

        return SharedLinkAccessResponse(
            share_id=share.id,
            resource_type=share.resource_type,
            resource_id=share.resource_id,
            role=_role_value(share.role),
            resource_name=self._resource_name(share.resource_type, share.resource_id),
        )

    def resolve_shared_item(
        self,
        *,
        resource_type: str,
        resource_id: UUID,
        user: User | None,
    ) -> ResolveSharedItemResponse:
        resource = self._get_resource(resource_type, resource_id)
        if resource is None or getattr(resource, "is_trashed", False):
            return ResolveSharedItemResponse(
                status="not_found",
                resource_type=resource_type,
                resource_id=resource_id,
            )

        name = resource.name
        owner = get_user_by_id(self.db, resource.owner_id)
        owner_email = owner.email if owner else None

        link = permissions.get_link_share_for_resource(
            self.db, resource_type=resource_type, resource_id=resource_id
        )
        if link is not None and link.token:
            return ResolveSharedItemResponse(
                status="public",
                resource_type=resource_type,
                resource_id=resource_id,
                resource_name=name,
                role=_role_value(link.role),
                link_token=link.token,
                owner_email=owner_email,
            )

        if user is not None:
            if resource_type == "file" and permissions.can_view_file(self.db, user, resource):
                return ResolveSharedItemResponse(
                    status="allowed",
                    resource_type=resource_type,
                    resource_id=resource_id,
                    resource_name=name,
                    role=permissions.role_for_file(self.db, user, resource),
                    owner_email=owner_email,
                )
            if resource_type == "folder" and permissions.can_view_folder(
                self.db, user, resource
            ):
                return ResolveSharedItemResponse(
                    status="allowed",
                    resource_type=resource_type,
                    resource_id=resource_id,
                    resource_name=name,
                    role=permissions.role_for_folder(self.db, user, resource),
                    owner_email=owner_email,
                )

        return ResolveSharedItemResponse(
            status="denied",
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=name,
            owner_email=owner_email,
        )

    def request_access(
        self,
        requester: User,
        *,
        resource_type: str,
        resource_id: UUID,
        role: str,
        message: str | None,
    ) -> AccessRequest:
        resource = self._get_resource(resource_type, resource_id)
        if resource is None or getattr(resource, "is_trashed", False):
            raise errors.not_found("Item not found")
        if resource.owner_id == requester.id:
            raise errors.bad_request("You already own this item")

        if resource_type == "file" and permissions.can_view_file(self.db, requester, resource):
            raise errors.bad_request("You already have access")
        if resource_type == "folder" and permissions.can_view_folder(
            self.db, requester, resource
        ):
            raise errors.bad_request("You already have access")

        existing = self.db.scalar(
            select(AccessRequest).where(
                AccessRequest.resource_type == resource_type,
                AccessRequest.resource_id == resource_id,
                AccessRequest.requester_id == requester.id,
                AccessRequest.status == AccessRequestStatus.pending,
            )
        )
        if existing is not None:
            existing.requested_role = ShareRole(role)
            existing.message = message
            self.db.commit()
            self.db.refresh(existing)
            return existing

        row = AccessRequest(
            owner_id=resource.owner_id,
            requester_id=requester.id,
            resource_type=resource_type,
            resource_id=resource_id,
            requested_role=ShareRole(role),
            message=message,
            status=AccessRequestStatus.pending,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_access_requests_for_resource(
        self,
        owner: User,
        *,
        resource_type: str,
        resource_id: UUID,
    ) -> list[AccessRequestResponse]:
        self._require_owned_resource(owner, resource_type, resource_id)
        rows = list(
            self.db.scalars(
                select(AccessRequest)
                .where(
                    AccessRequest.owner_id == owner.id,
                    AccessRequest.resource_type == resource_type,
                    AccessRequest.resource_id == resource_id,
                    AccessRequest.status == AccessRequestStatus.pending,
                )
                .order_by(AccessRequest.created_at.desc())
            ).all()
        )
        return [self._access_request_response(r) for r in rows]

    def approve_access_request(self, owner: User, request_id: UUID) -> Share:
        row = self.db.scalar(
            select(AccessRequest).where(
                AccessRequest.id == request_id,
                AccessRequest.owner_id == owner.id,
            )
        )
        if row is None:
            raise errors.not_found("Access request not found")
        if row.status != AccessRequestStatus.pending:
            raise errors.bad_request("Access request is not pending")

        requester = get_user_by_id(self.db, row.requester_id)
        if requester is None:
            raise errors.not_found("Requester not found")

        share = self.create_user_share(
            owner,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            grantee_email=requester.email,
            role=_role_value(row.requested_role),
        )
        row.status = AccessRequestStatus.approved
        self.db.commit()
        return share

    def deny_access_request(self, owner: User, request_id: UUID) -> None:
        row = self.db.scalar(
            select(AccessRequest).where(
                AccessRequest.id == request_id,
                AccessRequest.owner_id == owner.id,
            )
        )
        if row is None:
            raise errors.not_found("Access request not found")
        if row.status != AccessRequestStatus.pending:
            raise errors.bad_request("Access request is not pending")
        row.status = AccessRequestStatus.denied
        self.db.commit()

    def _access_request_response(self, row: AccessRequest) -> AccessRequestResponse:
        requester = get_user_by_id(self.db, row.requester_id)
        return AccessRequestResponse(
            id=row.id,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            requested_role=_role_value(row.requested_role),
            message=row.message,
            status=_role_value(row.status),
            requester_email=requester.email if requester else None,
            requester_display_name=requester.display_name if requester else None,
            resource_name=self._resource_name(row.resource_type, row.resource_id),
            created_at=row.created_at,
        )

    def _get_resource(self, resource_type: str, resource_id: UUID) -> File | Folder | None:
        if resource_type == "file":
            return file_queries.get_file_by_id(self.db, resource_id, include_trashed=True)
        return folder_queries.get_folder_by_id(self.db, resource_id)

    def list_link_contents(
        self, token: str, *, folder_id: UUID | None = None
    ) -> SharedLinkContentsResponse:
        share = permissions.get_share_by_token(self.db, token)
        if share is None:
            raise errors.not_found("Share link not found or expired")

        role = _role_value(share.role)
        resource_name = self._resource_name(share.resource_type, share.resource_id)

        if share.resource_type == "file":
            file_row = file_queries.get_file_by_id(self.db, share.resource_id)
            if file_row is None or file_row.is_trashed:
                raise errors.not_found("Shared file not found")
            return SharedLinkContentsResponse(
                share_id=share.id,
                resource_type="file",
                resource_id=share.resource_id,
                role=role,
                resource_name=resource_name,
                files=[self._anon_file_response(file_row, role)],
            )

        shared_root = folder_queries.get_folder_by_id(self.db, share.resource_id)
        if shared_root is None or shared_root.is_trashed:
            raise errors.not_found("Shared folder not found")

        current_id = folder_id or shared_root.id
        current = folder_queries.get_folder_by_id(self.db, current_id)
        if (
            current is None
            or current.is_trashed
            or not permissions.folder_is_within_shared_folder(current, shared_root.id)
        ):
            raise errors.not_found("Folder not found")

        child_folders = folder_queries.list_child_folders(
            self.db, owner_id=shared_root.owner_id, parent_folder_id=current.id
        )
        files = file_queries.list_files_in_folder(
            self.db, owner_id=shared_root.owner_id, folder_id=current.id
        )

        parent_folder_id: UUID | None = None
        if current.id != shared_root.id:
            parent_folder_id = current.parent_id

        return SharedLinkContentsResponse(
            share_id=share.id,
            resource_type="folder",
            resource_id=share.resource_id,
            role=role,
            resource_name=resource_name,
            current_folder_id=current.id,
            parent_folder_id=parent_folder_id,
            folders=[self._anon_folder_response(f, role) for f in child_folders],
            files=[self._anon_file_response(f, role) for f in files],
        )

    def request_link_download_url(
        self, token: str, file_id: UUID
    ) -> RequestDownloadUrlResponse:
        _share, file_row = self._require_link_file(token, file_id)
        if file_row.status != FileStatus.ready or file_row.object is None:
            raise errors.bad_request("File is not ready to download")

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

    def request_link_preview_url(self, token: str, file_id: UUID) -> PreviewUrlResponse:
        _share, file_row = self._require_link_file(token, file_id)
        if not is_media_mime(file_row.mime_type, file_row.name):
            raise errors.bad_request(
                "Inline preview is only available for images, RAW photos, and videos"
            )

        if is_raw_file(file_row.mime_type, file_row.name):
            preview_key = ensure_raw_preview_jpeg(self.db, file_row.id)
            if preview_key is None:
                return self._link_thumb_response(file_row)
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

    def request_link_thumbnail_url(self, token: str, file_id: UUID) -> PreviewUrlResponse:
        _share, file_row = self._require_link_file(token, file_id)
        if not is_media_mime(file_row.mime_type, file_row.name):
            raise errors.bad_request(
                "Thumbnails are only available for images, RAW photos, and videos"
            )
        return self._link_thumb_response(file_row)

    def _link_thumb_response(self, file_row: File) -> PreviewUrlResponse:
        thumb_key = s3_store.build_preview_object_key(
            str(file_row.owner_id), str(file_row.id), THUMB_VARIANT
        )
        if not s3_store.object_exists(bucket=file_row.object.s3_bucket, key=thumb_key):
            from service.thumbnail_service import generate_thumbnail_for_file

            generated = generate_thumbnail_for_file(self.db, file_row.id)
            if not generated or not s3_store.object_exists(
                bucket=file_row.object.s3_bucket, key=thumb_key
            ):
                raise errors.not_found("Thumbnail is not ready yet")

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

    def _require_link_file(self, token: str, file_id: UUID) -> tuple[Share, File]:
        share = permissions.get_share_by_token(self.db, token)
        if share is None:
            raise errors.not_found("Share link not found or expired")
        file_row = file_queries.get_file_by_id(self.db, file_id)
        if (
            file_row is None
            or file_row.is_trashed
            or not permissions.file_is_within_link_share(self.db, file_row, share)
        ):
            raise errors.not_found("File not found")
        if file_row.status != FileStatus.ready or file_row.object is None:
            raise errors.bad_request("File is not ready")
        return share, file_row

    def _anon_file_response(self, file_row: File, role: str) -> FileResponse:
        data = FileResponse.model_validate(file_row)
        return data.model_copy(update={"access_role": role})

    def _anon_folder_response(self, folder: Folder, role: str) -> FolderResponse:
        data = FolderResponse.model_validate(folder)
        return data.model_copy(update={"access_role": role})

    def _require_owned_resource(
        self, owner: User, resource_type: str, resource_id: UUID
    ) -> File | Folder:
        if resource_type == "file":
            file_row = file_queries.get_owned_file(
                self.db, owner_id=owner.id, file_id=resource_id
            )
            if file_row is None:
                raise errors.not_found("File not found")
            return file_row
        folder = folder_queries.get_owned_folder(
            self.db, owner_id=owner.id, folder_id=resource_id
        )
        if folder is None:
            raise errors.not_found("Folder not found")
        return folder

    def _resource_name(self, resource_type: str, resource_id: UUID) -> str:
        if resource_type == "file":
            file_row = self.db.scalar(select(File).where(File.id == resource_id))
            return file_row.name if file_row else "unknown"
        folder = self.db.scalar(select(Folder).where(Folder.id == resource_id))
        return folder.name if folder else "unknown"
