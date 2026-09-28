from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from dependencies.authentication import get_current_user
from dependencies.response import success
from dependencies.sql_session import get_db
from folders.schemas.folders import (
    CreateFolderRequest,
    MoveFolderRequest,
    OptionalUUID,
    RenameFolderRequest,
    FolderResponse,
)
from models import User
from service.folder_service import FolderService

router = APIRouter()


def get_folder_service(db: Session = Depends(get_db)) -> FolderService:
    return FolderService(db)


@router.post("", name="create folder")
def create_folder(
    body: CreateFolderRequest,
    current_user: User = Depends(get_current_user),
    folders: FolderService = Depends(get_folder_service),
):
    folder = folders.create_folder(
        current_user,
        name=body.name,
        parent_folder_id=body.parent_folder_id,
    )
    return success(
        data=FolderResponse.model_validate(folder),
        message="folder created",
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/contents", name="list folder contents")
def list_folder_contents(
    parent_folder_id: OptionalUUID = Query(default=None),
    current_user: User = Depends(get_current_user),
    folders: FolderService = Depends(get_folder_service),
):
    return success(data=folders.list_folder_contents(current_user, parent_folder_id))


@router.get("/tree", name="list folder tree")
def list_folder_tree(
    current_user: User = Depends(get_current_user),
    folders: FolderService = Depends(get_folder_service),
):
    return success(data=folders.list_folder_tree(current_user))


@router.get("/{folder_id}", name="get folder")
def get_folder(
    folder_id: UUID,
    current_user: User = Depends(get_current_user),
    folders: FolderService = Depends(get_folder_service),
):
    return success(data=folders.get_folder_response(current_user, folder_id))


@router.patch("/{folder_id}", name="rename folder")
def rename_folder(
    folder_id: UUID,
    body: RenameFolderRequest,
    current_user: User = Depends(get_current_user),
    folders: FolderService = Depends(get_folder_service),
):
    folder = folders.rename_folder(current_user, folder_id, body.name)
    return success(data=FolderResponse.model_validate(folder), message="folder renamed")


@router.post("/{folder_id}/move", name="move folder")
def move_folder(
    folder_id: UUID,
    body: MoveFolderRequest,
    current_user: User = Depends(get_current_user),
    folders: FolderService = Depends(get_folder_service),
):
    folder = folders.move_folder(
        current_user,
        folder_id,
        body.destination_parent_folder_id,
    )
    return success(data=FolderResponse.model_validate(folder), message="folder moved")


@router.post("/{folder_id}/trash", name="move folder to trash")
def move_folder_to_trash(
    folder_id: UUID,
    current_user: User = Depends(get_current_user),
    folders: FolderService = Depends(get_folder_service),
):
    folder = folders.move_folder_to_trash(current_user, folder_id)
    return success(data=FolderResponse.model_validate(folder), message="folder trashed")
