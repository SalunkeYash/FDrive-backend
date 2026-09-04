"""Trash retention and soft-delete helpers."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import TrashEntry


def trash_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=settings.trash_retention_days)


def create_trash_entry(
    db: Session,
    *,
    owner_id: UUID,
    resource_type: str,
    resource_id: UUID,
    original_folder_id: UUID | None,
) -> TrashEntry:
    entry = TrashEntry(
        owner_id=owner_id,
        resource_type=resource_type,
        resource_id=resource_id,
        original_folder_id=original_folder_id,
        expires_at=trash_expiry(),
    )
    db.add(entry)
    return entry


def get_open_trash_entry(
    db: Session,
    *,
    owner_id: UUID,
    resource_type: str,
    resource_id: UUID,
) -> TrashEntry | None:
    from sqlalchemy import select

    return db.scalar(
        select(TrashEntry).where(
            TrashEntry.owner_id == owner_id,
            TrashEntry.resource_type == resource_type,
            TrashEntry.resource_id == resource_id,
            TrashEntry.purged_at.is_(None),
        )
    )


def mark_trash_entry_purged(entry: TrashEntry | None) -> None:
    if entry is not None:
        entry.purged_at = datetime.now(UTC)
