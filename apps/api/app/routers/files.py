from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.files import (
    CopyFileRequest,
    FileResponse,
    MoveFileRequest,
    RenameFileRequest,
    RequestDownloadUrlResponse,
    RequestUploadUrlRequest,
    RequestUploadUrlResponse,
)
from app.services.files import FileService

router = APIRouter(prefix="/files", tags=["files"])


def get_file_service(db: Session = Depends(get_db)) -> FileService:
    return FileService(db)


@router.post(
    "/request-upload-url",
    response_model=RequestUploadUrlResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Get a presigned URL to upload a file directly to storage",
)
def request_upload_url(
    body: RequestUploadUrlRequest,
    current_user: User = Depends(get_current_user),
    files: FileService = Depends(get_file_service),
) -> RequestUploadUrlResponse:
    return files.request_upload_url(
        current_user,
        file_name=body.file_name,
        size_bytes=body.size_bytes,
        mime_type=body.mime_type,
        folder_id=body.folder_id,
    )


@router.get(
    "/list-folder-files",
    response_model=list[FileResponse],
    summary="List ready files in a folder (omit folder_id for root)",
)
def list_folder_files(
    folder_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    files: FileService = Depends(get_file_service),
) -> list[FileResponse]:
    return files.list_folder_files(current_user, folder_id)


@router.post(
    "/{file_id}/complete-upload",
    response_model=FileResponse,
    summary="Confirm the file finished uploading to storage",
)
def complete_upload(
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    files: FileService = Depends(get_file_service),
) -> FileResponse:
    file_row = files.complete_upload(current_user, file_id)
    return FileResponse.model_validate(file_row)


@router.get(
    "/{file_id}/get-file",
    response_model=FileResponse,
    summary="Get file metadata",
)
def get_file(
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    files: FileService = Depends(get_file_service),
) -> FileResponse:
    file_row = files.get_file(current_user, file_id)
    return FileResponse.model_validate(file_row)


@router.get(
    "/{file_id}/request-download-url",
    response_model=RequestDownloadUrlResponse,
    summary="Get a short-lived URL to download the file from storage",
)
def request_download_url(
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    files: FileService = Depends(get_file_service),
) -> RequestDownloadUrlResponse:
    return files.request_download_url(current_user, file_id)


@router.patch(
    "/{file_id}/rename-file",
    response_model=FileResponse,
    summary="Rename a file",
)
def rename_file(
    file_id: UUID,
    body: RenameFileRequest,
    current_user: User = Depends(get_current_user),
    files: FileService = Depends(get_file_service),
) -> FileResponse:
    file_row = files.rename_file(current_user, file_id, body.file_name)
    return FileResponse.model_validate(file_row)


@router.post(
    "/{file_id}/move-file",
    response_model=FileResponse,
    summary="Move a file into another folder (or root)",
)
def move_file(
    file_id: UUID,
    body: MoveFileRequest,
    current_user: User = Depends(get_current_user),
    files: FileService = Depends(get_file_service),
) -> FileResponse:
    file_row = files.move_file(current_user, file_id, body.destination_folder_id)
    return FileResponse.model_validate(file_row)


@router.post(
    "/{file_id}/copy-file",
    response_model=FileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Copy a file (duplicates storage bytes and counts toward quota)",
)
def copy_file(
    file_id: UUID,
    body: CopyFileRequest,
    current_user: User = Depends(get_current_user),
    files: FileService = Depends(get_file_service),
) -> FileResponse:
    file_row = files.copy_file(
        current_user,
        file_id,
        destination_folder_id=body.destination_folder_id,
        new_file_name=body.new_file_name,
    )
    return FileResponse.model_validate(file_row)
