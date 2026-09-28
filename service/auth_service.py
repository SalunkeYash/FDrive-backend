from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from dependencies import errors
from dependencies.config import settings
from dependencies.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    refresh_token_expiry,
    verify_password,
)
from models import RefreshToken, User
from auth.schemas.auth import TokenResponse
from model_handler.user_model_handler import create_user, get_user_by_email


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def register(self, email: str, password: str, display_name: str | None) -> TokenResponse:
        if get_user_by_email(self.db, email) is not None:
            raise errors.conflict("Email already registered")

        user = create_user(
            self.db,
            email=email,
            password_hash=hash_password(password),
            display_name=display_name,
        )

        tokens = self._create_token_pair(user)
        self.db.commit()
        return tokens

    def login(self, email: str, password: str) -> TokenResponse:
        user = get_user_by_email(self.db, email)
        if not self._password_matches(user, password):
            raise errors.unauthorized("Invalid email or password")

        # password matched ⇒ user exists
        assert user is not None
        if not user.is_active:
            raise errors.forbidden("Account is inactive")

        tokens = self._create_token_pair(user)
        self.db.commit()
        return tokens

    def refresh(self, refresh_token: str) -> TokenResponse:
        stored = self._require_active_refresh_token(refresh_token)
        user = stored.user
        if user is None or not user.is_active:
            raise errors.unauthorized("Invalid refresh token")

        self._revoke(stored)
        tokens = self._create_token_pair(user)
        self.db.commit()
        return tokens

    def logout(self, refresh_token: str) -> None:
        stored = self._find_refresh_token(refresh_token)
        if stored is not None and stored.revoked_at is None:
            self._revoke(stored)
            self.db.commit()

    def _password_matches(self, user: User | None, password: str) -> bool:
        if user is None or user.password_hash is None:
            return False
        return verify_password(user.password_hash, password)

    def _find_refresh_token(self, refresh_token: str) -> RefreshToken | None:
        token_hash = hash_refresh_token(refresh_token)
        return self.db.scalar(
            select(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .options(joinedload(RefreshToken.user))
        )

    def _require_active_refresh_token(self, refresh_token: str) -> RefreshToken:
        stored = self._find_refresh_token(refresh_token)
        now = datetime.now(UTC)
        if stored is None or stored.revoked_at is not None or stored.expires_at <= now:
            raise errors.unauthorized("Invalid or expired refresh token")
        return stored

    def _revoke(self, stored: RefreshToken) -> None:
        stored.revoked_at = datetime.now(UTC)

    def _create_token_pair(self, user: User) -> TokenResponse:
        raw_refresh = generate_refresh_token()
        self.db.add(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_refresh_token(raw_refresh),
                expires_at=refresh_token_expiry(),
            )
        )
        return TokenResponse(
            access_token=create_access_token(user_id=user.id, email=user.email),
            refresh_token=raw_refresh,
            expires_in=settings.access_token_expire_minutes * 60,
        )
