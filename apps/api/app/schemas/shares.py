from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CreateUserShareRequest(BaseModel):
    resource_type: str = Field(pattern="^(file|folder)$")
    resource_id: UUID
    grantee_email: EmailStr
    role: str = Field(default="viewer", pattern="^(viewer|editor)$")


class CreateLinkShareRequest(BaseModel):
    resource_type: str = Field(pattern="^(file|folder)$")
    resource_id: UUID
    role: str = Field(default="viewer", pattern="^(viewer|editor)$")


class ShareResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    resource_type: str
    resource_id: UUID
    grantee_user_id: UUID | None
    role: str
    token: str | None
    expires_at: datetime | None
    created_at: datetime


class SharedLinkAccessResponse(BaseModel):
    share_id: UUID
    resource_type: str
    resource_id: UUID
    role: str
    resource_name: str


class SharedWithMeItem(BaseModel):
    share_id: UUID
    resource_type: str
    resource_id: UUID
    role: str
    resource_name: str
    mime_type: str | None = None
    size_bytes: int | None = None
    folder_id: UUID | None = None
    parent_id: UUID | None = None
    updated_at: datetime | None = None
    is_trashed: bool = False
