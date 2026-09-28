from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from models import File, FileStatus, Folder, User
from files.schemas.files import FileResponse
from folders.schemas.folders import FolderResponse
from search.schemas.search import SearchDriveResponse
from model_handler import folder_model_handler as folder_queries
from service import permission_service as permissions


class SearchService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def search_drive(self, user: User, query: str) -> SearchDriveResponse:
        term = f"%{query.strip()}%"
        shared_file_ids, accessible_folder_ids = self._shared_access_ids(user.id)

        file_access = [File.owner_id == user.id]
        if shared_file_ids:
            file_access.append(File.id.in_(shared_file_ids))
        if accessible_folder_ids:
            file_access.append(File.folder_id.in_(accessible_folder_ids))

        files = list(
            self.db.scalars(
                select(File)
                .where(
                    File.is_trashed.is_(False),
                    File.status == FileStatus.ready,
                    File.name.ilike(term),
                    or_(*file_access),
                )
                .order_by(File.name.asc())
                .limit(50)
            ).all()
        )

        folder_access = [Folder.owner_id == user.id]
        if accessible_folder_ids:
            folder_access.append(Folder.id.in_(accessible_folder_ids))

        folders = list(
            self.db.scalars(
                select(Folder)
                .where(
                    Folder.is_trashed.is_(False),
                    Folder.name.ilike(term),
                    or_(*folder_access),
                )
                .order_by(Folder.name.asc())
                .limit(50)
            ).all()
        )

        return SearchDriveResponse(
            query=query.strip(),
            files=[
                FileResponse.model_validate(f).model_copy(
                    update={"access_role": permissions.role_for_file(self.db, user, f)}
                )
                for f in files
            ],
            folders=[
                FolderResponse.model_validate(folder).model_copy(
                    update={
                        "access_role": permissions.role_for_folder(
                            self.db, user, folder
                        )
                    }
                )
                for folder in folders
            ],
        )

    def _shared_access_ids(self, user_id: UUID) -> tuple[list[UUID], list[UUID]]:
        """Direct shared file IDs + shared folders including descendants."""
        shares = permissions.list_shares_with_me(self.db, user_id)
        shared_file_ids = [s.resource_id for s in shares if s.resource_type == "file"]
        shared_folder_ids = [
            s.resource_id for s in shares if s.resource_type == "folder"
        ]

        accessible: set[UUID] = set()
        for folder_id in shared_folder_ids:
            folder = folder_queries.get_folder_by_id(self.db, folder_id)
            if folder is None or folder.is_trashed:
                continue
            accessible.add(folder.id)
            marker = f"{folder.path}{folder.id}/"
            descendants = self.db.scalars(
                select(Folder.id).where(
                    Folder.owner_id == folder.owner_id,
                    Folder.is_trashed.is_(False),
                    Folder.path.startswith(marker),
                )
            ).all()
            accessible.update(descendants)

        return shared_file_ids, list(accessible)
