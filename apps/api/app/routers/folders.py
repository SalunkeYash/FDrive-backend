from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.folders import (
    CreateFolderRequest,
    FolderContentsResponse,
    FolderResponse,
    FolderTreeNode,
    MoveFolderRequest,
    OptionalUUID,
    RenameFolderRequest,
)
from app.services.folders import FolderService

router = APIRouter(prefix="/folders", tags=["folders"])


def get_folder_service(db: Session = Depends(get_db)) -> FolderService:
    return FolderService(db)


@router.post(
    "/create-folder",
    response_model=FolderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a folder in the drive",
)
def create_folder(
    body: CreateFolderRequest,
    current_user: User = Depends(get_current_user),
    folders: FolderService = Depends(get_folder_service),
) -> FolderResponse:
    folder = folders.create_folder(
        current_user,
        name=body.name,
        parent_folder_id=body.parent_folder_id,
    )
    return FolderResponse.model_validate(folder)


@router.get(
    "/list-folder-contents",
    response_model=FolderContentsResponse,
    summary="List folders inside a parent folder (omit parent for root)",
)
def list_folder_contents(
    parent_folder_id: OptionalUUID = Query(default=None),
    current_user: User = Depends(get_current_user),
    folders: FolderService = Depends(get_folder_service),
) -> FolderContentsResponse:
    return folders.list_folder_contents(current_user, parent_folder_id)


@router.get(
    "/list-folder-tree",
    response_model=list[FolderTreeNode],
    summary="Get the full folder tree for the signed-in user",
)
def list_folder_tree(
    current_user: User = Depends(get_current_user),
    folders: FolderService = Depends(get_folder_service),
) -> list[FolderTreeNode]:
    return folders.list_folder_tree(current_user)


@router.get(
    "/{folder_id}/get-folder",
    response_model=FolderResponse,
    summary="Get one folder by id",
)
def get_folder(
    folder_id: UUID,
    current_user: User = Depends(get_current_user),
    folders: FolderService = Depends(get_folder_service),
) -> FolderResponse:
    folder = folders.get_folder(current_user, folder_id)
    return FolderResponse.model_validate(folder)


@router.patch(
    "/{folder_id}/rename-folder",
    response_model=FolderResponse,
    summary="Rename a folder",
)
def rename_folder(
    folder_id: UUID,
    body: RenameFolderRequest,
    current_user: User = Depends(get_current_user),
    folders: FolderService = Depends(get_folder_service),
) -> FolderResponse:
    folder = folders.rename_folder(current_user, folder_id, body.name)
    return FolderResponse.model_validate(folder)


@router.post(
    "/{folder_id}/move-folder",
    response_model=FolderResponse,
    summary="Move a folder under a different parent",
)
def move_folder(
    folder_id: UUID,
    body: MoveFolderRequest,
    current_user: User = Depends(get_current_user),
    folders: FolderService = Depends(get_folder_service),
) -> FolderResponse:
    folder = folders.move_folder(
        current_user,
        folder_id,
        body.destination_parent_folder_id,
    )
    return FolderResponse.model_validate(folder)


@router.post(
    "/{folder_id}/move-folder-to-trash",
    response_model=FolderResponse,
    summary="Soft-delete a folder (and its subfolders)",
)
def move_folder_to_trash(
    folder_id: UUID,
    current_user: User = Depends(get_current_user),
    folders: FolderService = Depends(get_folder_service),
) -> FolderResponse:
    folder = folders.move_folder_to_trash(current_user, folder_id)
    return FolderResponse.model_validate(folder)
