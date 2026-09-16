from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RequestUploadUrlRequest(BaseModel):
    file_name: str = Field(min_length=1, max_length=512)
    size_bytes: int = Field(gt=0)
    mime_type: str | None = Field(default=None, max_length=255)
    folder_id: UUID | None = None


class RequestUploadUrlResponse(BaseModel):
    file_id: UUID
    upload_url: str
    upload_method: str = "PUT"
    required_headers: dict[str, str]
    s3_key: str
    expires_in_seconds: int


class FileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    name: str
    mime_type: str | None
    size_bytes: int
    status: str
    folder_id: UUID | None
    is_trashed: bool
    created_at: datetime
    updated_at: datetime
    # Populated by API when useful for the current user (owner | viewer | editor)
    access_role: str | None = None


class RequestDownloadUrlResponse(BaseModel):
    file_id: UUID
    file_name: str
    download_url: str
    download_method: str = "GET"
    expires_in_seconds: int
    size_bytes: int
    mime_type: str | None


class RenameFileRequest(BaseModel):
    file_name: str = Field(min_length=1, max_length=512)


class MoveFileRequest(BaseModel):
    destination_folder_id: UUID | None = None


class CopyFileRequest(BaseModel):
    destination_folder_id: UUID | None = None
    new_file_name: str | None = Field(default=None, min_length=1, max_length=512)
