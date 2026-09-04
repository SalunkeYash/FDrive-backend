from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import File, FileStatus, Folder, User
from app.schemas.files import FileResponse
from app.schemas.folders import FolderResponse
from app.schemas.search import SearchDriveResponse


class SearchService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def search_drive(self, owner: User, query: str) -> SearchDriveResponse:
        term = f"%{query.strip()}%"
        files = list(
            self.db.scalars(
                select(File).where(
                    File.owner_id == owner.id,
                    File.is_trashed.is_(False),
                    File.status == FileStatus.ready,
                    File.name.ilike(term),
                ).order_by(File.name.asc()).limit(50)
            ).all()
        )
        folders = list(
            self.db.scalars(
                select(Folder).where(
                    Folder.owner_id == owner.id,
                    Folder.is_trashed.is_(False),
                    Folder.name.ilike(term),
                ).order_by(Folder.name.asc()).limit(50)
            ).all()
        )
        return SearchDriveResponse(
            query=query.strip(),
            files=[FileResponse.model_validate(f) for f in files],
            folders=[FolderResponse.model_validate(f) for f in folders],
        )
