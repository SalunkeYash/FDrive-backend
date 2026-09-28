"""Reusable user lookups and profile updates."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from dependencies.config import settings
from models import User


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == normalize_email(email)))


def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    return db.scalar(select(User).where(User.id == user_id))


def create_user(
    db: Session,
    *,
    email: str,
    password_hash: str,
    display_name: str | None = None,
) -> User:
    """Create a user with the default storage quota. Caller commits."""
    user = User(
        email=normalize_email(email),
        password_hash=password_hash,
        display_name=display_name,
        bytes_used=0,
        bytes_limit=settings.default_bytes_limit,
    )
    db.add(user)
    db.flush()
    return user


def update_display_name(user: User, display_name: str | None) -> User:
    user.display_name = display_name
    return user
