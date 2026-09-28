from pydantic import BaseModel, Field

from files.schemas.files import FileResponse
from folders.schemas.folders import FolderResponse


class SearchDriveResponse(BaseModel):
    query: str
    files: list[FileResponse]
    folders: list[FolderResponse]


class SearchQuery(BaseModel):
    q: str = Field(min_length=1, max_length=200)
