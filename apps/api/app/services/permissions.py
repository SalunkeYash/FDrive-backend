"""Permission checks for owners and share grantees (including folder inheritance)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import errors
from app.models import File, Folder, Share, ShareRole, User
from app.services import folder_queries as fq


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


def get_link_share_for_resource(
    db: Session, *, resource_type: str, resource_id: UUID
) -> Share | None:
    """Public link share: grantee is null and a token is set."""
    share = db.scalar(
        select(Share).where(
            Share.resource_type == resource_type,
            Share.resource_id == resource_id,
            Share.grantee_user_id.is_(None),
            Share.token.is_not(None),
        )
    )
    if share is not None and _share_active(share):
        return share
    return None


def folder_is_within_shared_folder(folder: Folder, shared_root_id: UUID) -> bool:
    if folder.id == shared_root_id:
        return True
    return str(shared_root_id) in [
        part for part in folder.path.strip("/").split("/") if part
    ]


def file_is_within_link_share(db: Session, file_row: File, share: Share) -> bool:
    if share.resource_type == "file":
        return file_row.id == share.resource_id
    if file_row.folder_id is None:
        return False
    folder = fq.get_folder_by_id(db, file_row.folder_id)
    if folder is None or folder.is_trashed:
        return False
    return folder_is_within_shared_folder(folder, share.resource_id)



def _folder_and_ancestor_ids(folder: Folder) -> list[UUID]:
    """Closest-first: folder itself, then parents from path."""
    ids: list[UUID] = [folder.id]
    for part in reversed(folder.path.strip("/").split("/")):
        if part:
            ids.append(UUID(part))
    return ids


def get_effective_folder_share(
    db: Session, *, user_id: UUID, folder: Folder
) -> Share | None:
    """Direct folder share, or share on an ancestor folder."""
    for folder_id in _folder_and_ancestor_ids(folder):
        share = get_share_for_user(
            db, user_id=user_id, resource_type="folder", resource_id=folder_id
        )
        if share is not None:
            return share
    return None


def get_effective_file_share(db: Session, *, user_id: UUID, file_row: File) -> Share | None:
    """Direct file share, or share on the containing folder / ancestors."""
    direct = get_share_for_user(
        db, user_id=user_id, resource_type="file", resource_id=file_row.id
    )
    if direct is not None:
        return direct
    if file_row.folder_id is None:
        return None
    folder = fq.get_folder_by_id(db, file_row.folder_id)
    if folder is None or folder.is_trashed:
        return None
    return get_effective_folder_share(db, user_id=user_id, folder=folder)


def can_view_file(db: Session, user: User, file_row: File) -> bool:
    if file_row.is_trashed:
        return file_row.owner_id == user.id
    if file_row.owner_id == user.id:
        return True
    return get_effective_file_share(db, user_id=user.id, file_row=file_row) is not None


def can_edit_file(db: Session, user: User, file_row: File) -> bool:
    if file_row.is_trashed:
        return file_row.owner_id == user.id
    if file_row.owner_id == user.id:
        return True
    share = get_effective_file_share(db, user_id=user.id, file_row=file_row)
    return share is not None and share.role == ShareRole.editor


def can_view_folder(db: Session, user: User, folder: Folder) -> bool:
    if folder.is_trashed:
        return folder.owner_id == user.id
    if folder.owner_id == user.id:
        return True
    return get_effective_folder_share(db, user_id=user.id, folder=folder) is not None


def can_edit_folder(db: Session, user: User, folder: Folder) -> bool:
    if folder.is_trashed:
        return folder.owner_id == user.id
    if folder.owner_id == user.id:
        return True
    share = get_effective_folder_share(db, user_id=user.id, folder=folder)
    return share is not None and share.role == ShareRole.editor


def role_for_file(db: Session, user: User, file_row: File) -> str | None:
    if file_row.owner_id == user.id:
        return "owner"
    share = get_effective_file_share(db, user_id=user.id, file_row=file_row)
    if share is None:
        return None
    return share.role.value if hasattr(share.role, "value") else str(share.role)


def role_for_folder(db: Session, user: User, folder: Folder) -> str | None:
    if folder.owner_id == user.id:
        return "owner"
    share = get_effective_folder_share(db, user_id=user.id, folder=folder)
    if share is None:
        return None
    return share.role.value if hasattr(share.role, "value") else str(share.role)


def require_view_file(db: Session, user: User, file_id: UUID) -> File:
    from app.services import file_queries as file_q

    file_row = file_q.get_file_by_id(db, file_id)
    if file_row is None or not can_view_file(db, user, file_row):
        raise errors.not_found("File not found")
    return file_row


def require_edit_file(db: Session, user: User, file_id: UUID) -> File:
    from app.services import file_queries as file_q

    file_row = file_q.get_file_by_id(db, file_id)
    if file_row is None or not can_edit_file(db, user, file_row):
        raise errors.not_found("File not found")
    return file_row


def require_view_folder(db: Session, user: User, folder_id: UUID) -> Folder:
    folder = fq.get_folder_by_id(db, folder_id)
    if folder is None or folder.is_trashed or not can_view_folder(db, user, folder):
        raise errors.not_found("Folder not found")
    return folder


def require_edit_folder(db: Session, user: User, folder_id: UUID) -> Folder:
    folder = fq.get_folder_by_id(db, folder_id)
    if folder is None or folder.is_trashed or not can_edit_folder(db, user, folder):
        raise errors.not_found("Folder not found")
    return folder


def list_shares_for_owner(db: Session, owner_id: UUID) -> list[Share]:
    return list(
        db.scalars(
            select(Share)
            .where(Share.owner_id == owner_id)
            .order_by(Share.created_at.desc())
        ).all()
    )


def list_user_shares_for_resource(
    db: Session, *, owner_id: UUID, resource_type: str, resource_id: UUID
) -> list[Share]:
    shares = list(
        db.scalars(
            select(Share)
            .where(
                Share.owner_id == owner_id,
                Share.resource_type == resource_type,
                Share.resource_id == resource_id,
                Share.grantee_user_id.is_not(None),
            )
            .order_by(Share.created_at.asc())
        ).all()
    )
    return [s for s in shares if _share_active(s)]


def list_shares_with_me(db: Session, user_id: UUID) -> list[Share]:
    shares = list(
        db.scalars(
            select(Share)
            .where(Share.grantee_user_id == user_id)
            .order_by(Share.created_at.desc())
        ).all()
    )
    return [s for s in shares if _share_active(s)]
