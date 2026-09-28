from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from dependencies.authentication import get_current_user
from dependencies.response import success
from dependencies.sql_session import get_db
from files.schemas.files import (
    CopyFileRequest,
    FileResponse,
    MoveFileRequest,
    RenameFileRequest,
    RequestUploadUrlRequest,
)
from models import User
from service.file_service import FileService

router = APIRouter()


def get_file_service(db: Session = Depends(get_db)) -> FileService:
    return FileService(db)


@router.post("/upload-url", name="request upload url")
def request_upload_url(
    body: RequestUploadUrlRequest,
    current_user: User = Depends(get_current_user),
    files: FileService = Depends(get_file_service),
):
    data = files.request_upload_url(
        current_user,
        file_name=body.file_name,
        size_bytes=body.size_bytes,
        mime_type=body.mime_type,
        folder_id=body.folder_id,
    )
    return success(data=data, status_code=status.HTTP_201_CREATED)


@router.get("", name="list folder files")
def list_folder_files(
    folder_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    files: FileService = Depends(get_file_service),
):
    return success(data=files.list_folder_files(current_user, folder_id))


@router.post("/{file_id}/complete-upload", name="complete upload")
def complete_upload(
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    files: FileService = Depends(get_file_service),
):
    file_row = files.complete_upload(current_user, file_id)
    return success(data=FileResponse.model_validate(file_row), message="upload completed")


@router.get("/{file_id}", name="get file")
def get_file(
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    files: FileService = Depends(get_file_service),
):
    return success(data=files.get_file_response(current_user, file_id))


@router.get("/{file_id}/download-url", name="request download url")
def request_download_url(
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    files: FileService = Depends(get_file_service),
):
    return success(data=files.request_download_url(current_user, file_id))


@router.patch("/{file_id}", name="rename file")
def rename_file(
    file_id: UUID,
    body: RenameFileRequest,
    current_user: User = Depends(get_current_user),
    files: FileService = Depends(get_file_service),
):
    file_row = files.rename_file(current_user, file_id, body.file_name)
    return success(data=FileResponse.model_validate(file_row), message="file renamed")


@router.post("/{file_id}/move", name="move file")
def move_file(
    file_id: UUID,
    body: MoveFileRequest,
    current_user: User = Depends(get_current_user),
    files: FileService = Depends(get_file_service),
):
    file_row = files.move_file(current_user, file_id, body.destination_folder_id)
    return success(data=FileResponse.model_validate(file_row), message="file moved")


@router.post("/{file_id}/copy", name="copy file")
def copy_file(
    file_id: UUID,
    body: CopyFileRequest,
    current_user: User = Depends(get_current_user),
    files: FileService = Depends(get_file_service),
):
    file_row = files.copy_file(
        current_user,
        file_id,
        destination_folder_id=body.destination_folder_id,
        new_file_name=body.new_file_name,
    )
    return success(
        data=FileResponse.model_validate(file_row),
        message="file copied",
        status_code=status.HTTP_201_CREATED,
    )
