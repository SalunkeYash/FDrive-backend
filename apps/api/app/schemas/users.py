from pydantic import BaseModel, Field

from app.schemas.auth import UserResponse


class UpdateProfileRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)


class StorageQuotaResponse(BaseModel):
    bytes_used: int
    bytes_limit: int
    bytes_remaining: int
    usage_percent: float


__all__ = ["StorageQuotaResponse", "UpdateProfileRequest", "UserResponse"]
