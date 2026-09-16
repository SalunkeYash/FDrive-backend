"""Reusable file lookups and name helpers."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import File, FileStatus


def normalize_file_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("File name cannot be empty")
    if "/" in cleaned or "\\" in cleaned:
        raise ValueError("File name cannot contain path separators")
    return cleaned


def get_file_by_id(
    db: Session,
    file_id: UUID,
    *,
    include_trashed: bool = False,
) -> File | None:
    query = (
        select(File)
        .where(File.id == file_id)
        .options(joinedload(File.object))
    )
    if not include_trashed:
        query = query.where(File.is_trashed.is_(False))
    return db.scalar(query)


def get_owned_file(
    db: Session,
    *,
    owner_id: UUID,
    file_id: UUID,
    include_trashed: bool = False,
) -> File | None:
    file_row = get_file_by_id(db, file_id, include_trashed=include_trashed)
    if file_row is None or file_row.owner_id != owner_id:
        return None
    return file_row


def list_files_in_folder(
    db: Session,
    *,
    owner_id: UUID,
    folder_id: UUID | None,
) -> list[File]:
    query = select(File).where(
        File.owner_id == owner_id,
        File.is_trashed.is_(False),
        File.status == FileStatus.ready,
    )
    if folder_id is None:
        query = query.where(File.folder_id.is_(None))
    else:
        query = query.where(File.folder_id == folder_id)
    return list(db.scalars(query.order_by(File.name.asc())).all())


def list_trashed_files(db: Session, owner_id: UUID) -> list[File]:
    return list(
        db.scalars(
            select(File)
            .where(File.owner_id == owner_id, File.is_trashed.is_(True))
            .options(joinedload(File.object))
            .order_by(File.trashed_at.desc())
        ).all()
    )
