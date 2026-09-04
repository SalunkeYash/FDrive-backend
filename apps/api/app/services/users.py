"""Reusable user lookups used by auth and later phases."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == normalize_email(email)))


def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    return db.scalar(select(User).where(User.id == user_id))
