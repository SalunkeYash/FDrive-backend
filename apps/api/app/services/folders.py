from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core import errors
from app.models import Folder, User
from app.schemas.folders import FolderContentsResponse, FolderResponse, FolderTreeNode
from app.services import folder_queries as fq


class FolderService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_folder(
        self,
        owner: User,
        *,
        name: str,
        parent_folder_id: UUID | None,
    ) -> Folder:
        try:
            name = fq.normalize_folder_name(name)
        except ValueError as exc:
            raise errors.bad_request(str(exc)) from exc

        parent = self._require_parent(owner.id, parent_folder_id)
        if fq.sibling_name_exists(
            self.db,
            owner_id=owner.id,
            parent_folder_id=parent_folder_id,
            name=name,
        ):
            raise errors.conflict("A folder with this name already exists here")

        folder = Folder(
            owner_id=owner.id,
            parent_id=parent_folder_id,
            name=name,
            path=fq.build_child_path(parent),
        )
        self.db.add(folder)
        self.db.commit()
        self.db.refresh(folder)
        return folder

    def get_folder(self, owner: User, folder_id: UUID) -> Folder:
        return self._require_owned_folder(owner.id, folder_id)

    def list_folder_contents(
        self,
        owner: User,
        parent_folder_id: UUID | None,
    ) -> FolderContentsResponse:
        if parent_folder_id is not None:
            self._require_owned_folder(owner.id, parent_folder_id)

        folders = fq.list_child_folders(
            self.db,
            owner_id=owner.id,
            parent_folder_id=parent_folder_id,
        )
        return FolderContentsResponse(
            parent_folder_id=parent_folder_id,
            folders=[FolderResponse.model_validate(f) for f in folders],
        )

    def rename_folder(self, owner: User, folder_id: UUID, name: str) -> Folder:
        try:
            name = fq.normalize_folder_name(name)
        except ValueError as exc:
            raise errors.bad_request(str(exc)) from exc

        folder = self._require_owned_folder(owner.id, folder_id)
        if fq.sibling_name_exists(
            self.db,
            owner_id=owner.id,
            parent_folder_id=folder.parent_id,
            name=name,
            exclude_folder_id=folder.id,
        ):
            raise errors.conflict("A folder with this name already exists here")

        folder.name = name
        self.db.commit()
        self.db.refresh(folder)
        return folder

    def move_folder(
        self,
        owner: User,
        folder_id: UUID,
        destination_parent_folder_id: UUID | None,
    ) -> Folder:
        folder = self._require_owned_folder(owner.id, folder_id)
        destination = self._require_parent(owner.id, destination_parent_folder_id)

        if destination is not None and (
            destination.id == folder.id or fq.is_descendant(folder, destination)
        ):
            raise errors.bad_request("Cannot move a folder into itself or a subfolder")

        if fq.sibling_name_exists(
            self.db,
            owner_id=owner.id,
            parent_folder_id=destination_parent_folder_id,
            name=folder.name,
            exclude_folder_id=folder.id,
        ):
            raise errors.conflict("A folder with this name already exists in the destination")

        old_prefix = f"{folder.path}{folder.id}/"
        new_path = fq.build_child_path(destination)
        new_prefix = f"{new_path}{folder.id}/"

        folder.parent_id = destination_parent_folder_id
        folder.path = new_path

        # Rewrite materialized paths for all descendants
        descendants = [
            child
            for child in fq.list_owned_folders(self.db, owner.id)
            if child.path.startswith(old_prefix)
        ]
        for child in descendants:
            child.path = new_prefix + child.path[len(old_prefix) :]

        self.db.commit()
        self.db.refresh(folder)
        return folder

    def move_folder_to_trash(self, owner: User, folder_id: UUID) -> Folder:
        folder = self._require_owned_folder(owner.id, folder_id)
        now = datetime.now(UTC)
        folder.is_trashed = True
        folder.trashed_at = now

        # Soft-trash descendants so they disappear from the tree
        prefix = f"{folder.path}{folder.id}/"
        for child in fq.list_owned_folders(self.db, owner.id):
            if child.path.startswith(prefix):
                child.is_trashed = True
                child.trashed_at = now

        self.db.commit()
        self.db.refresh(folder)
        return folder

    def list_folder_tree(self, owner: User) -> list[FolderTreeNode]:
        folders = fq.list_owned_folders(self.db, owner.id)
        nodes = {
            f.id: FolderTreeNode(
                id=f.id,
                name=f.name,
                parent_id=f.parent_id,
                path=f.path,
                children=[],
            )
            for f in folders
        }
        roots: list[FolderTreeNode] = []
        for folder in folders:
            node = nodes[folder.id]
            if folder.parent_id is None or folder.parent_id not in nodes:
                roots.append(node)
            else:
                nodes[folder.parent_id].children.append(node)
        return roots

    def _require_owned_folder(self, owner_id: UUID, folder_id: UUID) -> Folder:
        folder = fq.get_owned_folder(self.db, owner_id=owner_id, folder_id=folder_id)
        if folder is None:
            raise errors.not_found("Folder not found")
        return folder

    def _require_parent(self, owner_id: UUID, parent_folder_id: UUID | None) -> Folder | None:
        if parent_folder_id is None:
            return None
        return self._require_owned_folder(owner_id, parent_folder_id)
