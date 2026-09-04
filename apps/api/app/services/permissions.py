"""Permission checks for owners and share grantees."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import File, Folder, Share, ShareRole, User


def _share_active(share: Share) -> bool:
    if share.expires_at is not None and share.expires_at <= datetime.now(UTC):
        return False
    return True


def get_share_for_user(
    db: Session,
    *,
    user_id: UUID,
    resource_type: str,
    resource_id: UUID,
) -> Share | None:
    share = db.scalar(
        select(Share).where(
            Share.resource_type == resource_type,
            Share.resource_id == resource_id,
            Share.grantee_user_id == user_id,
        )
    )
    if share is not None and _share_active(share):
        return share
    return None


def get_share_by_token(db: Session, token: str) -> Share | None:
    share = db.scalar(select(Share).where(Share.token == token))
    if share is not None and _share_active(share):
        return share
    return None


def can_view_file(db: Session, user: User, file_row: File) -> bool:
    if file_row.owner_id == user.id:
        return True
    return get_share_for_user(
        db, user_id=user.id, resource_type="file", resource_id=file_row.id
    ) is not None


def can_edit_file(db: Session, user: User, file_row: File) -> bool:
    if file_row.owner_id == user.id:
        return True
    share = get_share_for_user(
        db, user_id=user.id, resource_type="file", resource_id=file_row.id
    )
    return share is not None and share.role == ShareRole.editor


def can_view_folder(db: Session, user: User, folder: Folder) -> bool:
    if folder.owner_id == user.id:
        return True
    return get_share_for_user(
        db, user_id=user.id, resource_type="folder", resource_id=folder.id
    ) is not None


def list_shares_for_owner(db: Session, owner_id: UUID) -> list[Share]:
    return list(
        db.scalars(
            select(Share)
            .where(Share.owner_id == owner_id)
            .order_by(Share.created_at.desc())
        ).all()
    )


def list_shares_with_me(db: Session, user_id: UUID) -> list[Share]:
    return list(
        db.scalars(
            select(Share).where(
                or_(Share.grantee_user_id == user_id),
            ).order_by(Share.created_at.desc())
        ).all()
    )
