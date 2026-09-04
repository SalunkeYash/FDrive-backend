from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base, TimestampMixin


class FileStatus(enum.StrEnum):
    pending = "pending"
    ready = "ready"
    failed = "failed"


class ShareRole(enum.StrEnum):
    viewer = "viewer"
    editor = "editor"


class UploadSessionStatus(enum.StrEnum):
    initiated = "initiated"
    uploading = "uploading"
    completed = "completed"
    aborted = "aborted"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    # Quota (Phase 04 will enforce; schema ready now)
    bytes_used: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    bytes_limit: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=str(5 * 1024 * 1024 * 1024),  # 5 GiB default free tier
    )

    folders: Mapped[list[Folder]] = relationship(back_populates="owner")
    files: Mapped[list[File]] = relationship(back_populates="owner")
    shares_owned: Mapped[list[Share]] = relationship(
        back_populates="owner",
        foreign_keys="Share.owner_id",
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(back_populates="user")


class Folder(Base, TimestampMixin):
    __tablename__ = "folders"
    __table_args__ = (
        UniqueConstraint("owner_id", "parent_id", "name", name="uq_folders_owner_parent_name"),
        Index("ix_folders_owner_parent", "owner_id", "parent_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Materialized path for tree queries (e.g. /uuid/uuid/); filled in Phase 05
    path: Mapped[str] = mapped_column(String(2048), nullable=False, server_default="/")
    is_trashed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    trashed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped[User] = relationship(back_populates="folders")
    parent: Mapped[Folder | None] = relationship(
        remote_side="Folder.id",
        back_populates="children",
    )
    children: Mapped[list[Folder]] = relationship(back_populates="parent")
    files: Mapped[list[File]] = relationship(back_populates="folder")


class File(Base, TimestampMixin):
    __tablename__ = "files"
    __table_args__ = (
        Index("ix_files_owner_folder", "owner_id", "folder_id"),
        Index("ix_files_owner_name", "owner_id", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    folder_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    status: Mapped[FileStatus] = mapped_column(
        Enum(FileStatus, name="file_status", native_enum=True),
        nullable=False,
        server_default="pending",
    )
    is_trashed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    trashed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped[User] = relationship(back_populates="files")
    folder: Mapped[Folder | None] = relationship(back_populates="files")
    object: Mapped[FileObject | None] = relationship(
        back_populates="file",
        uselist=False,
        cascade="all, delete-orphan",
    )
    upload_sessions: Mapped[list[UploadSession]] = relationship(back_populates="file")


class FileObject(Base, TimestampMixin):
    """S3 object metadata — bytes live in object storage, not Postgres."""

    __tablename__ = "file_objects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    s3_bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_class: Mapped[str | None] = mapped_column(String(64), nullable=True)

    file: Mapped[File] = relationship(back_populates="object")


class Share(Base, TimestampMixin):
    __tablename__ = "shares"
    __table_args__ = (
        Index("ix_shares_resource", "resource_type", "resource_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # "file" | "folder"
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # Null grantee + token = public link share (Phase 10)
    grantee_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    role: Mapped[ShareRole] = mapped_column(
        Enum(ShareRole, name="share_role", native_enum=True),
        nullable=False,
        server_default="viewer",
    )
    token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped[User] = relationship(back_populates="shares_owned", foreign_keys=[owner_id])


class TrashEntry(Base, TimestampMixin):
    """Soft-delete ledger for purge scheduling (Phase 09)."""

    __tablename__ = "trash_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    original_folder_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UploadSession(Base, TimestampMixin):
    """Multipart / resumable upload state (Phase 14)."""

    __tablename__ = "upload_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    s3_upload_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[UploadSessionStatus] = mapped_column(
        Enum(UploadSessionStatus, name="upload_session_status", native_enum=True),
        nullable=False,
        server_default="initiated",
    )
    parts_completed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_parts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    file: Mapped[File] = relationship(back_populates="upload_sessions")


class RefreshToken(Base, TimestampMixin):
    """Opaque refresh tokens stored hashed for rotation / logout (Phase 03)."""

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="refresh_tokens")
