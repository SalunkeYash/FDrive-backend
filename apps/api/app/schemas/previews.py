from uuid import UUID

from pydantic import BaseModel, Field


class PreviewUrlResponse(BaseModel):
    file_id: UUID
    variant: str = Field(description="thumbnail or preview")
    preview_url: str
    expires_in_seconds: int
    mime_type: str | None = None
