from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def blank_as_none(value: Any) -> Any:
    """Swagger often sends the string 'null' instead of JSON null."""
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in {"", "null", "none"}:
        return None
    return value


OptionalUUID = Annotated[UUID | None, BeforeValidator(blank_as_none)]


class CreateFolderRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"name": "Documents"},
            ]
        }
    )

    name: str = Field(min_length=1, max_length=255)
    parent_folder_id: OptionalUUID = Field(
        default=None,
        description=(
            "Existing folder to create inside. "
            "Omit the field (or JSON null) for the drive root."
        ),
    )


class RenameFolderRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class MoveFolderRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"destination_parent_folder_id": None},
            ]
        }
    )

    destination_parent_folder_id: OptionalUUID = Field(
        default=None,
        description="Folder to move into. Omit the field (or JSON null) to move to the drive root.",
    )


class FolderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    name: str
    parent_id: UUID | None
    path: str
    is_trashed: bool
    created_at: datetime
    updated_at: datetime
    access_role: str | None = None


class FolderContentsResponse(BaseModel):
    parent_folder_id: UUID | None
    folders: list[FolderResponse]


class FolderTreeNode(BaseModel):
    id: UUID
    name: str
    parent_id: UUID | None
    path: str
    children: list["FolderTreeNode"] = []
