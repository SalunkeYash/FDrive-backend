from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from dependencies.authentication import get_current_user
from dependencies.response import success
from dependencies.sql_session import get_db
from files.schemas.files import FileResponse
from folders.schemas.folders import FolderResponse
from models import User
from service.trash_service import TrashService

router = APIRouter()


def get_trash_service(db: Session = Depends(get_db)) -> TrashService:
    return TrashService(db)


@router.get("", name="list trash items")
def list_trash_items(
    current_user: User = Depends(get_current_user),
    trash: TrashService = Depends(get_trash_service),
):
    return success(data=trash.list_trash(current_user))


@router.post("/files/{file_id}", name="move file to trash")
def move_file_to_trash(
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    trash: TrashService = Depends(get_trash_service),
):
    file_row = trash.move_file_to_trash(current_user, file_id)
    return success(data=FileResponse.model_validate(file_row), message="file trashed")


@router.post("/files/{file_id}/restore", name="restore file from trash")
def restore_file_from_trash(
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    trash: TrashService = Depends(get_trash_service),
):
    file_row = trash.restore_file_from_trash(current_user, file_id)
    return success(data=FileResponse.model_validate(file_row), message="file restored")


@router.post("/files/{file_id}/delete", name="permanently delete file")
def permanently_delete_file(
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    trash: TrashService = Depends(get_trash_service),
):
    trash.permanently_delete_file(current_user, file_id)
    return success(message="file deleted")


@router.post("/folders/{folder_id}", name="move folder to trash")
def move_folder_to_trash(
    folder_id: UUID,
    current_user: User = Depends(get_current_user),
    trash: TrashService = Depends(get_trash_service),
):
    folder = trash.move_folder_to_trash(current_user, folder_id)
    return success(data=FolderResponse.model_validate(folder), message="folder trashed")


@router.post("/folders/{folder_id}/restore", name="restore folder from trash")
def restore_folder_from_trash(
    folder_id: UUID,
    current_user: User = Depends(get_current_user),
    trash: TrashService = Depends(get_trash_service),
):
    folder = trash.restore_folder_from_trash(current_user, folder_id)
    return success(data=FolderResponse.model_validate(folder), message="folder restored")


@router.post("/folders/{folder_id}/delete", name="permanently delete folder")
def permanently_delete_folder(
    folder_id: UUID,
    current_user: User = Depends(get_current_user),
    trash: TrashService = Depends(get_trash_service),
):
    trash.permanently_delete_folder(current_user, folder_id)
    return success(message="folder deleted")
