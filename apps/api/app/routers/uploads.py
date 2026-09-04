from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.files import FileResponse
from app.schemas.uploads import (
    CompleteMultipartUploadRequest,
    GetPartUploadUrlRequest,
    GetPartUploadUrlResponse,
    InitiateMultipartUploadRequest,
    InitiateMultipartUploadResponse,
)
from app.services.multipart_uploads import MultipartUploadService

router = APIRouter(prefix="/uploads", tags=["uploads"])


def get_multipart_service(db: Session = Depends(get_db)) -> MultipartUploadService:
    return MultipartUploadService(db)


@router.post(
    "/initiate-multipart-upload",
    response_model=InitiateMultipartUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a large/resumable multipart upload",
)
def initiate_multipart_upload(
    body: InitiateMultipartUploadRequest,
    current_user: User = Depends(get_current_user),
    uploads: MultipartUploadService = Depends(get_multipart_service),
) -> InitiateMultipartUploadResponse:
    return uploads.initiate(
        current_user,
        file_name=body.file_name,
        size_bytes=body.size_bytes,
        mime_type=body.mime_type,
        folder_id=body.folder_id,
        part_size_bytes=body.part_size_bytes,
    )


@router.post(
    "/{upload_session_id}/get-part-upload-url",
    response_model=GetPartUploadUrlResponse,
    summary="Get a presigned URL for one multipart part",
)
def get_part_upload_url(
    upload_session_id: UUID,
    body: GetPartUploadUrlRequest,
    current_user: User = Depends(get_current_user),
    uploads: MultipartUploadService = Depends(get_multipart_service),
) -> GetPartUploadUrlResponse:
    return uploads.get_part_upload_url(current_user, upload_session_id, body.part_number)


@router.post(
    "/{upload_session_id}/complete-multipart-upload",
    response_model=FileResponse,
    summary="Finish a multipart upload after all parts are uploaded",
)
def complete_multipart_upload(
    upload_session_id: UUID,
    body: CompleteMultipartUploadRequest,
    current_user: User = Depends(get_current_user),
    uploads: MultipartUploadService = Depends(get_multipart_service),
) -> FileResponse:
    file_row = uploads.complete(current_user, upload_session_id, body)
    return FileResponse.model_validate(file_row)


@router.post(
    "/{upload_session_id}/abort-multipart-upload",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Abort an in-progress multipart upload",
)
def abort_multipart_upload(
    upload_session_id: UUID,
    current_user: User = Depends(get_current_user),
    uploads: MultipartUploadService = Depends(get_multipart_service),
) -> None:
    uploads.abort(current_user, upload_session_id)
