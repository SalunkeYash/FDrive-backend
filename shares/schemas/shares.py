from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from files.schemas.files import FileResponse, RequestDownloadUrlResponse
from folders.schemas.folders import FolderResponse
from previews.schemas.previews import PreviewUrlResponse


class CreateUserShareRequest(BaseModel):
    resource_type: str = Field(pattern="^(file|folder)$")
    resource_id: UUID
    grantee_email: EmailStr
    role: str = Field(default="viewer", pattern="^(viewer|editor)$")


class CreateLinkShareRequest(BaseModel):
    resource_type: str = Field(pattern="^(file|folder)$")
    resource_id: UUID
    role: str = Field(default="viewer", pattern="^(viewer|editor)$")


class SetLinkAccessRequest(BaseModel):
    """Drive-style general access: restricted | anyone (with the link)."""

    resource_type: str = Field(pattern="^(file|folder)$")
    resource_id: UUID
    access: str = Field(pattern="^(restricted|anyone)$")
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


class ResourceAccessPerson(BaseModel):
    share_id: UUID | None = None
    email: str
    display_name: str | None = None
    role: str


class ResourceLinkAccess(BaseModel):
    enabled: bool
    share_id: UUID | None = None
    token: str | None = None
    role: str | None = None


class ResourceAccessResponse(BaseModel):
    resource_type: str
    resource_id: UUID
    owner: ResourceAccessPerson
    people: list[ResourceAccessPerson]
    link: ResourceLinkAccess


class SharedLinkAccessResponse(BaseModel):
    share_id: UUID
    resource_type: str
    resource_id: UUID
    role: str
    resource_name: str


class SharedLinkContentsResponse(BaseModel):
    share_id: UUID
    resource_type: str
    resource_id: UUID
    role: str
    resource_name: str
    current_folder_id: UUID | None = None
    parent_folder_id: UUID | None = None
    folders: list[FolderResponse] = []
    files: list[FileResponse] = []


class ResolveSharedItemResponse(BaseModel):
    """How a stable /open/{type}/{id} link should behave."""

    status: str  # public | allowed | denied | not_found
    resource_type: str
    resource_id: UUID
    resource_name: str | None = None
    role: str | None = None
    link_token: str | None = None
    owner_email: str | None = None


class RequestAccessRequest(BaseModel):
    resource_type: str = Field(pattern="^(file|folder)$")
    resource_id: UUID
    role: str = Field(default="viewer", pattern="^(viewer|editor)$")
    message: str | None = Field(default=None, max_length=1000)


class AccessRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    resource_type: str
    resource_id: UUID
    requested_role: str
    message: str | None
    status: str
    requester_email: str | None = None
    requester_display_name: str | None = None
    resource_name: str | None = None
    created_at: datetime


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


# Re-export for router typing convenience
__all__ = [
    "CreateUserShareRequest",
    "CreateLinkShareRequest",
    "SetLinkAccessRequest",
    "ShareResponse",
    "ResourceAccessPerson",
    "ResourceLinkAccess",
    "ResourceAccessResponse",
    "SharedLinkAccessResponse",
    "SharedLinkContentsResponse",
    "SharedWithMeItem",
    "RequestDownloadUrlResponse",
    "PreviewUrlResponse",
]
