from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from dependencies import errors
from models import Folder, User
from folders.schemas.folders import FolderContentsResponse, FolderResponse, FolderTreeNode
from model_handler import folder_model_handler as fq
from service import permission_service as permissions
from model_handler.user_model_handler import get_user_by_id


def _folder_response(db: Session, user: User, folder: Folder) -> FolderResponse:
    data = FolderResponse.model_validate(folder)
    return data.model_copy(
        update={"access_role": permissions.role_for_folder(db, user, folder)}
    )


class FolderService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_folder(
        self,
        user: User,
        *,
        name: str,
        parent_folder_id: UUID | None,
    ) -> Folder:
        try:
            name = fq.normalize_folder_name(name)
        except ValueError as exc:
            raise errors.bad_request(str(exc)) from exc

        drive_owner = user
        parent: Folder | None = None
        if parent_folder_id is not None:
            parent = permissions.require_edit_folder(self.db, user, parent_folder_id)
            if parent.owner_id != user.id:
                owner = get_user_by_id(self.db, parent.owner_id)
                if owner is None:
                    raise errors.not_found("Folder owner not found")
                drive_owner = owner
        else:
            # Creating at root is always in the caller's own drive.
            pass

        if fq.sibling_name_exists(
            self.db,
            owner_id=drive_owner.id,
            parent_folder_id=parent_folder_id,
            name=name,
        ):
            raise errors.conflict("A folder with this name already exists here")

        folder = Folder(
            owner_id=drive_owner.id,
            parent_id=parent_folder_id,
            name=name,
            path=fq.build_child_path(parent),
        )
        self.db.add(folder)
        self.db.commit()
        self.db.refresh(folder)
        return folder

    def get_folder(self, user: User, folder_id: UUID) -> Folder:
        return permissions.require_view_folder(self.db, user, folder_id)

    def get_folder_response(self, user: User, folder_id: UUID) -> FolderResponse:
        folder = self.get_folder(user, folder_id)
        return _folder_response(self.db, user, folder)

    def list_folder_contents(
        self,
        user: User,
        parent_folder_id: UUID | None,
    ) -> FolderContentsResponse:
        if parent_folder_id is not None:
            parent = permissions.require_view_folder(self.db, user, parent_folder_id)
            drive_owner_id = parent.owner_id
        else:
            drive_owner_id = user.id

        folders = fq.list_child_folders(
            self.db,
            owner_id=drive_owner_id,
            parent_folder_id=parent_folder_id,
        )
        if parent_folder_id is None:
            visible = folders
        else:
            visible = [f for f in folders if permissions.can_view_folder(self.db, user, f)]

        return FolderContentsResponse(
            parent_folder_id=parent_folder_id,
            folders=[_folder_response(self.db, user, f) for f in visible],
        )

    def rename_folder(self, user: User, folder_id: UUID, name: str) -> Folder:
        try:
            name = fq.normalize_folder_name(name)
        except ValueError as exc:
            raise errors.bad_request(str(exc)) from exc

        folder = permissions.require_edit_folder(self.db, user, folder_id)
        if fq.sibling_name_exists(
            self.db,
            owner_id=folder.owner_id,
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
        user: User,
        folder_id: UUID,
        destination_parent_folder_id: UUID | None,
    ) -> Folder:
        folder = permissions.require_edit_folder(self.db, user, folder_id)

        if destination_parent_folder_id is None:
            if user.id != folder.owner_id:
                raise errors.forbidden("Editors cannot move folders to another user's root")
            destination = None
        else:
            destination = permissions.require_edit_folder(
                self.db, user, destination_parent_folder_id
            )
            if destination.owner_id != folder.owner_id:
                raise errors.bad_request("Destination must stay in the same drive")

        if destination is not None and (
            destination.id == folder.id or fq.is_descendant(folder, destination)
        ):
            raise errors.bad_request("Cannot move a folder into itself or a subfolder")

        if fq.sibling_name_exists(
            self.db,
            owner_id=folder.owner_id,
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

        descendants = [
            child
            for child in fq.list_owned_folders(self.db, folder.owner_id)
            if child.path.startswith(old_prefix)
        ]
        for child in descendants:
            child.path = new_prefix + child.path[len(old_prefix) :]

        self.db.commit()
        self.db.refresh(folder)
        return folder

    def move_folder_to_trash(self, owner: User, folder_id: UUID) -> Folder:
        from service.trash_service import TrashService

        return TrashService(self.db).move_folder_to_trash(owner, folder_id)

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
