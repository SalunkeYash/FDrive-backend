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
    name: str
    mime_type: str | None
    size_bytes: int
    status: str
    folder_id: UUID | None
    is_trashed: bool
    created_at: datetime
    updated_at: datetime
