from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.files import FileResponse
from app.schemas.folders import FolderResponse
from app.schemas.trash import TrashListResponse
from app.services.trash import TrashService

router = APIRouter(prefix="/trash", tags=["trash"])


def get_trash_service(db: Session = Depends(get_db)) -> TrashService:
    return TrashService(db)


@router.get(
    "/list-trash-items",
    response_model=TrashListResponse,
    summary="List files and folders currently in trash",
)
def list_trash_items(
    current_user: User = Depends(get_current_user),
    trash: TrashService = Depends(get_trash_service),
) -> TrashListResponse:
    return trash.list_trash(current_user)


@router.post(
    "/files/{file_id}/move-file-to-trash",
    response_model=FileResponse,
    summary="Move a file to trash",
)
def move_file_to_trash(
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    trash: TrashService = Depends(get_trash_service),
) -> FileResponse:
    file_row = trash.move_file_to_trash(current_user, file_id)
    return FileResponse.model_validate(file_row)


@router.post(
    "/files/{file_id}/restore-file-from-trash",
    response_model=FileResponse,
    summary="Restore a file from trash",
)
def restore_file_from_trash(
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    trash: TrashService = Depends(get_trash_service),
) -> FileResponse:
    file_row = trash.restore_file_from_trash(current_user, file_id)
    return FileResponse.model_validate(file_row)


@router.post(
    "/files/{file_id}/permanently-delete-file",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete a file from trash (and storage)",
)
def permanently_delete_file(
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    trash: TrashService = Depends(get_trash_service),
) -> Response:
    trash.permanently_delete_file(current_user, file_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/folders/{folder_id}/move-folder-to-trash",
    response_model=FolderResponse,
    summary="Move a folder (and its contents) to trash",
)
def move_folder_to_trash(
    folder_id: UUID,
    current_user: User = Depends(get_current_user),
    trash: TrashService = Depends(get_trash_service),
) -> FolderResponse:
    folder = trash.move_folder_to_trash(current_user, folder_id)
    return FolderResponse.model_validate(folder)


@router.post(
    "/folders/{folder_id}/restore-folder-from-trash",
    response_model=FolderResponse,
    summary="Restore a folder (and its contents) from trash",
)
def restore_folder_from_trash(
    folder_id: UUID,
    current_user: User = Depends(get_current_user),
    trash: TrashService = Depends(get_trash_service),
) -> FolderResponse:
    folder = trash.restore_folder_from_trash(current_user, folder_id)
    return FolderResponse.model_validate(folder)


@router.post(
    "/folders/{folder_id}/permanently-delete-folder",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete a folder and its contents",
)
def permanently_delete_folder(
    folder_id: UUID,
    current_user: User = Depends(get_current_user),
    trash: TrashService = Depends(get_trash_service),
) -> Response:
    trash.permanently_delete_folder(current_user, folder_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
