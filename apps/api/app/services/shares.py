from __future__ import annotations

import secrets
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import errors
from app.models import File, Folder, Share, ShareRole, User
from app.schemas.shares import SharedLinkAccessResponse, ShareResponse, SharedWithMeItem
from app.services import file_queries, folder_queries, permissions
from app.services.users import get_user_by_email


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
        self._require_owned_resource(owner, resource_type, resource_id)
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

    def list_my_shares(self, owner: User) -> list[ShareResponse]:
        shares = permissions.list_shares_for_owner(self.db, owner.id)
        return [ShareResponse.model_validate(s) for s in shares]

    def list_shared_with_me(self, user: User) -> list[SharedWithMeItem]:
        shares = permissions.list_shares_with_me(self.db, user.id)
        items: list[SharedWithMeItem] = []
        for share in shares:
            role = share.role.value if hasattr(share.role, "value") else str(share.role)
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
            role=share.role.value if hasattr(share.role, "value") else str(share.role),
            resource_name=self._resource_name(share.resource_type, share.resource_id),
        )

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
