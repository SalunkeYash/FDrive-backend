from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core import errors
from app.integrations import s3 as s3_store
from app.models import File, FileStatus, Folder, User
from app.schemas.trash import TrashItem, TrashListResponse
from app.services import file_queries as file_q
from app.services import folder_queries as folder_q
from app.services import quota
from app.services import trash_entries as trash_q


class TrashService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_trash(self, owner: User) -> TrashListResponse:
        trashed_folders = folder_q.list_trashed_folders(self.db, owner.id)
        trashed_folder_ids = {f.id for f in trashed_folders}

        folder_items: list[TrashItem] = []
        for folder in trashed_folders:
            # Show only top-level trash roots (parent not also in trash)
            if folder.parent_id is None or folder.parent_id not in trashed_folder_ids:
                folder_items.append(
                    TrashItem(
                        resource_type="folder",
                        resource_id=folder.id,
                        name=folder.name,
                        trashed_at=folder.trashed_at,
                    )
                )

        file_items = [
            TrashItem(
                resource_type="file",
                resource_id=f.id,
                name=f.name,
                trashed_at=f.trashed_at,
                size_bytes=f.size_bytes,
            )
            for f in file_q.list_trashed_files(self.db, owner.id)
            # Hide files that belong to a trashed folder (they restore with the folder)
            if f.folder_id is None or f.folder_id not in trashed_folder_ids
        ]

        items = file_items + folder_items
        items.sort(
            key=lambda i: i.trashed_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        return TrashListResponse(items=items)

    def move_file_to_trash(self, owner: User, file_id: UUID) -> File:
        file_row = file_q.get_owned_file(self.db, owner_id=owner.id, file_id=file_id)
        if file_row is None:
            raise errors.not_found("File not found")

        now = datetime.now(UTC)
        file_row.is_trashed = True
        file_row.trashed_at = now
        trash_q.create_trash_entry(
            self.db,
            owner_id=owner.id,
            resource_type="file",
            resource_id=file_row.id,
            original_folder_id=file_row.folder_id,
        )
        self.db.commit()
        self.db.refresh(file_row)
        return file_row

    def restore_file_from_trash(self, owner: User, file_id: UUID) -> File:
        file_row = file_q.get_owned_file(
            self.db, owner_id=owner.id, file_id=file_id, include_trashed=True
        )
        if file_row is None or not file_row.is_trashed:
            raise errors.not_found("Trashed file not found")

        entry = trash_q.get_open_trash_entry(
            self.db, owner_id=owner.id, resource_type="file", resource_id=file_id
        )
        restore_folder_id = entry.original_folder_id if entry else None
        if restore_folder_id is not None:
            parent = folder_q.get_owned_folder(
                self.db, owner_id=owner.id, folder_id=restore_folder_id
            )
            if parent is None:
                restore_folder_id = None

        file_row.is_trashed = False
        file_row.trashed_at = None
        file_row.folder_id = restore_folder_id
        trash_q.mark_trash_entry_purged(entry)
        self.db.commit()
        self.db.refresh(file_row)
        return file_row

    def permanently_delete_file(self, owner: User, file_id: UUID) -> None:
        file_row = file_q.get_owned_file(
            self.db, owner_id=owner.id, file_id=file_id, include_trashed=True
        )
        if file_row is None:
            raise errors.not_found("File not found")
        self._purge_file(owner, file_row)
        self.db.commit()

    def move_folder_to_trash(self, owner: User, folder_id: UUID) -> Folder:
        folder = folder_q.get_owned_folder(self.db, owner_id=owner.id, folder_id=folder_id)
        if folder is None:
            raise errors.not_found("Folder not found")

        now = datetime.now(UTC)
        subtree = self._folder_subtree(owner.id, folder)
        folder_ids = {f.id for f in subtree}

        for node in subtree:
            node.is_trashed = True
            node.trashed_at = now

        for file_row in self._files_in_folders(owner.id, folder_ids):
            file_row.is_trashed = True
            file_row.trashed_at = now

        trash_q.create_trash_entry(
            self.db,
            owner_id=owner.id,
            resource_type="folder",
            resource_id=folder.id,
            original_folder_id=folder.parent_id,
        )
        self.db.commit()
        self.db.refresh(folder)
        return folder

    def restore_folder_from_trash(self, owner: User, folder_id: UUID) -> Folder:
        folder = folder_q.get_owned_folder(
            self.db, owner_id=owner.id, folder_id=folder_id, include_trashed=True
        )
        if folder is None or not folder.is_trashed:
            raise errors.not_found("Trashed folder not found")

        # Capture subtree using current (pre-restore) paths
        subtree = self._folder_subtree(owner.id, folder, include_trashed=True)
        folder_ids = {f.id for f in subtree}

        entry = trash_q.get_open_trash_entry(
            self.db, owner_id=owner.id, resource_type="folder", resource_id=folder_id
        )
        restore_parent_id = entry.original_folder_id if entry else None
        if restore_parent_id is not None:
            parent = folder_q.get_owned_folder(
                self.db, owner_id=owner.id, folder_id=restore_parent_id
            )
            if parent is None:
                restore_parent_id = None
                new_root_path = "/"
            else:
                new_root_path = f"{parent.path}{parent.id}/"
        else:
            new_root_path = "/"

        old_prefix = f"{folder.path}{folder.id}/"
        new_prefix = f"{new_root_path}{folder.id}/"

        folder.parent_id = restore_parent_id
        folder.path = new_root_path
        folder.is_trashed = False
        folder.trashed_at = None

        for child in subtree:
            if child.id == folder.id:
                continue
            if child.path.startswith(old_prefix):
                child.path = new_prefix + child.path[len(old_prefix) :]
            child.is_trashed = False
            child.trashed_at = None

        for file_row in self._files_in_folders(owner.id, folder_ids, trashed_only=True):
            file_row.is_trashed = False
            file_row.trashed_at = None

        trash_q.mark_trash_entry_purged(entry)
        self.db.commit()
        self.db.refresh(folder)
        return folder

    def permanently_delete_folder(self, owner: User, folder_id: UUID) -> None:
        folder = folder_q.get_owned_folder(
            self.db, owner_id=owner.id, folder_id=folder_id, include_trashed=True
        )
        if folder is None:
            raise errors.not_found("Folder not found")

        subtree = self._folder_subtree(owner.id, folder, include_trashed=True)
        folder_ids = {f.id for f in subtree}

        for file_row in self._files_in_folders(owner.id, folder_ids):
            self._purge_file(owner, file_row)

        for node in sorted(subtree, key=lambda f: len(f.path), reverse=True):
            entry = trash_q.get_open_trash_entry(
                self.db, owner_id=owner.id, resource_type="folder", resource_id=node.id
            )
            trash_q.mark_trash_entry_purged(entry)
            self.db.delete(node)

        self.db.commit()

    def _folder_subtree(
        self,
        owner_id: UUID,
        folder: Folder,
        *,
        include_trashed: bool = False,
    ) -> list[Folder]:
        folders = (
            folder_q.list_all_owned_folders(self.db, owner_id)
            if include_trashed
            else folder_q.list_owned_folders(self.db, owner_id)
        )
        prefix = f"{folder.path}{folder.id}/"
        return [folder] + [f for f in folders if f.id != folder.id and f.path.startswith(prefix)]

    def _files_in_folders(
        self,
        owner_id: UUID,
        folder_ids: set[UUID],
        *,
        trashed_only: bool = False,
    ) -> list[File]:
        query = (
            select(File)
            .where(File.owner_id == owner_id, File.folder_id.in_(folder_ids))
            .options(joinedload(File.object))
        )
        if trashed_only:
            query = query.where(File.is_trashed.is_(True))
        return list(self.db.scalars(query).all())

    def _purge_file(self, owner: User, file_row: File) -> None:
        if file_row.status == FileStatus.ready and file_row.size_bytes > 0:
            quota.release_bytes_used(owner, file_row.size_bytes)

        if file_row.object is not None:
            try:
                s3_store.delete_object(
                    bucket=file_row.object.s3_bucket,
                    key=file_row.object.s3_key,
                )
            except Exception:
                pass

        entry = trash_q.get_open_trash_entry(
            self.db,
            owner_id=owner.id,
            resource_type="file",
            resource_id=file_row.id,
        )
        trash_q.mark_trash_entry_purged(entry)
        self.db.delete(file_row)
