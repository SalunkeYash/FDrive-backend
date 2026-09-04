from uuid import UUID

from pydantic import BaseModel, Field


class InitiateMultipartUploadRequest(BaseModel):
    file_name: str = Field(min_length=1, max_length=512)
    size_bytes: int = Field(gt=0)
    mime_type: str | None = None
    folder_id: UUID | None = None
    part_size_bytes: int = Field(default=8 * 1024 * 1024, ge=5 * 1024 * 1024)


class InitiateMultipartUploadResponse(BaseModel):
    file_id: UUID
    upload_session_id: UUID
    s3_upload_id: str
    s3_key: str
    part_size_bytes: int
    total_parts: int


class GetPartUploadUrlRequest(BaseModel):
    part_number: int = Field(ge=1, le=10000)


class GetPartUploadUrlResponse(BaseModel):
    upload_url: str
    part_number: int
    expires_in_seconds: int


class CompletedPart(BaseModel):
    part_number: int
    etag: str


class CompleteMultipartUploadRequest(BaseModel):
    parts: list[CompletedPart]
