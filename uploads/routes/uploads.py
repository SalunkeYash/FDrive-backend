from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from dependencies.authentication import get_current_user
from dependencies.response import success
from dependencies.sql_session import get_db
from files.schemas.files import FileResponse
from models import User
from service.multipart_upload_service import MultipartUploadService
from uploads.schemas.uploads import (
    CompleteMultipartUploadRequest,
    GetPartUploadUrlRequest,
    InitiateMultipartUploadRequest,
)

router = APIRouter()


def get_multipart_service(db: Session = Depends(get_db)) -> MultipartUploadService:
    return MultipartUploadService(db)


@router.post("/multipart", name="initiate multipart upload")
def initiate_multipart_upload(
    body: InitiateMultipartUploadRequest,
    current_user: User = Depends(get_current_user),
    uploads: MultipartUploadService = Depends(get_multipart_service),
):
    data = uploads.initiate(
        current_user,
        file_name=body.file_name,
        size_bytes=body.size_bytes,
        mime_type=body.mime_type,
        folder_id=body.folder_id,
        part_size_bytes=body.part_size_bytes,
    )
    return success(data=data, status_code=status.HTTP_201_CREATED)


@router.post("/{upload_session_id}/parts", name="get part upload url")
def get_part_upload_url(
    upload_session_id: UUID,
    body: GetPartUploadUrlRequest,
    current_user: User = Depends(get_current_user),
    uploads: MultipartUploadService = Depends(get_multipart_service),
):
    return success(
        data=uploads.get_part_upload_url(current_user, upload_session_id, body.part_number)
    )


@router.post("/{upload_session_id}/complete", name="complete multipart upload")
def complete_multipart_upload(
    upload_session_id: UUID,
    body: CompleteMultipartUploadRequest,
    current_user: User = Depends(get_current_user),
    uploads: MultipartUploadService = Depends(get_multipart_service),
):
    file_row = uploads.complete(current_user, upload_session_id, body)
    return success(data=FileResponse.model_validate(file_row), message="upload completed")


@router.post("/{upload_session_id}/abort", name="abort multipart upload")
def abort_multipart_upload(
    upload_session_id: UUID,
    current_user: User = Depends(get_current_user),
    uploads: MultipartUploadService = Depends(get_multipart_service),
):
    uploads.abort(current_user, upload_session_id)
    return success(message="upload aborted")
