from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.previews import PreviewUrlResponse
from app.services.previews import PreviewService

router = APIRouter(prefix="/previews", tags=["previews"])


def get_preview_service(db: Session = Depends(get_db)) -> PreviewService:
    return PreviewService(db)


@router.get(
    "/{file_id}/request-thumbnail-url",
    response_model=PreviewUrlResponse,
    summary="Get a presigned URL for an image thumbnail",
)
def request_thumbnail_url(
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    previews: PreviewService = Depends(get_preview_service),
) -> PreviewUrlResponse:
    return previews.request_thumbnail_url(current_user, file_id)


@router.get(
    "/{file_id}/request-preview-url",
    response_model=PreviewUrlResponse,
    summary="Get a presigned inline preview URL for an image",
)
def request_preview_url(
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    previews: PreviewService = Depends(get_preview_service),
) -> PreviewUrlResponse:
    return previews.request_preview_url(current_user, file_id)
