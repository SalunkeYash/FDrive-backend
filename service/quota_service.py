"""Storage quota helpers — reused by upload and file lifecycle later."""

from __future__ import annotations

from dependencies import errors
from models import User


def bytes_remaining(user: User) -> int:
    return max(user.bytes_limit - user.bytes_used, 0)


def usage_percent(user: User) -> float:
    if user.bytes_limit <= 0:
        return 100.0
    return round((user.bytes_used / user.bytes_limit) * 100, 2)


def has_room(user: User, additional_bytes: int) -> bool:
    if additional_bytes < 0:
        raise ValueError("additional_bytes must be >= 0")
    return user.bytes_used + additional_bytes <= user.bytes_limit


def ensure_quota(user: User, additional_bytes: int) -> None:
    """Raise if the user cannot store `additional_bytes` more data."""
    if additional_bytes < 0:
        raise ValueError("additional_bytes must be >= 0")
    if not has_room(user, additional_bytes):
        raise errors.quota_exceeded(
            f"Storage quota exceeded: need {additional_bytes} bytes, "
            f"{bytes_remaining(user)} bytes remaining"
        )


def add_bytes_used(user: User, amount: int) -> None:
    """Increase used bytes after a successful upload. Call inside a DB transaction."""
    if amount < 0:
        raise ValueError("amount must be >= 0")
    ensure_quota(user, amount)
    user.bytes_used += amount


def release_bytes_used(user: User, amount: int) -> None:
    """Decrease used bytes after delete/purge. Never goes below zero."""
    if amount < 0:
        raise ValueError("amount must be >= 0")
    user.bytes_used = max(user.bytes_used - amount, 0)
