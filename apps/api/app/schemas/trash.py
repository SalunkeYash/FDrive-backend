from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TrashItem(BaseModel):
    resource_type: str  # "file" | "folder"
    resource_id: UUID
    name: str
    trashed_at: datetime | None
    size_bytes: int | None = None


class TrashListResponse(BaseModel):
    items: list[TrashItem]
