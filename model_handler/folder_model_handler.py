"""Reusable folder lookups and path helpers."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from models import Folder


def normalize_folder_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Folder name cannot be empty")
    if "/" in cleaned or "\\" in cleaned:
        raise ValueError("Folder name cannot contain path separators")
    return cleaned


def build_child_path(parent: Folder | None) -> str:
    """Materialized ancestor path for a new child folder."""
    if parent is None:
        return "/"
    return f"{parent.path}{parent.id}/"


def get_folder_by_id(db: Session, folder_id: UUID) -> Folder | None:
    return db.scalar(select(Folder).where(Folder.id == folder_id))


def get_owned_folder(
    db: Session,
    *,
    owner_id: UUID,
    folder_id: UUID,
    include_trashed: bool = False,
) -> Folder | None:
    query = select(Folder).where(Folder.id == folder_id, Folder.owner_id == owner_id)
    if not include_trashed:
        query = query.where(Folder.is_trashed.is_(False))
    return db.scalar(query)


def list_child_folders(
    db: Session,
    *,
    owner_id: UUID,
    parent_folder_id: UUID | None,
) -> list[Folder]:
    query: Select[tuple[Folder]] = select(Folder).where(
        Folder.owner_id == owner_id,
        Folder.is_trashed.is_(False),
    )
    if parent_folder_id is None:
        query = query.where(Folder.parent_id.is_(None))
    else:
        query = query.where(Folder.parent_id == parent_folder_id)

    query = query.order_by(Folder.name.asc())
    return list(db.scalars(query).all())


def sibling_name_exists(
    db: Session,
    *,
    owner_id: UUID,
    parent_folder_id: UUID | None,
    name: str,
    exclude_folder_id: UUID | None = None,
) -> bool:
    query = select(Folder.id).where(
        Folder.owner_id == owner_id,
        Folder.name == name,
        Folder.is_trashed.is_(False),
    )
    if parent_folder_id is None:
        query = query.where(Folder.parent_id.is_(None))
    else:
        query = query.where(Folder.parent_id == parent_folder_id)

    if exclude_folder_id is not None:
        query = query.where(Folder.id != exclude_folder_id)

    return db.scalar(query) is not None


def list_owned_folders(db: Session, owner_id: UUID) -> list[Folder]:
    return list(
        db.scalars(
            select(Folder)
            .where(Folder.owner_id == owner_id, Folder.is_trashed.is_(False))
            .order_by(Folder.path.asc(), Folder.name.asc())
        ).all()
    )


def list_trashed_folders(db: Session, owner_id: UUID) -> list[Folder]:
    return list(
        db.scalars(
            select(Folder)
            .where(Folder.owner_id == owner_id, Folder.is_trashed.is_(True))
            .order_by(Folder.trashed_at.desc())
        ).all()
    )


def list_all_owned_folders(db: Session, owner_id: UUID) -> list[Folder]:
    """Active + trashed folders for subtree operations."""
    return list(
        db.scalars(
            select(Folder)
            .where(Folder.owner_id == owner_id)
            .order_by(Folder.path.asc(), Folder.name.asc())
        ).all()
    )


def is_descendant(possible_ancestor: Folder, possible_descendant: Folder) -> bool:
    """True if `possible_descendant` lives under `possible_ancestor` in the tree."""
    marker = f"{possible_ancestor.path}{possible_ancestor.id}/"
    return possible_descendant.path.startswith(marker)
