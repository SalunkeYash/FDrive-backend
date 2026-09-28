from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from dependencies.authentication import get_current_user
from dependencies.response import success
from dependencies.sql_session import get_db
from models import User
from service.preview_service import PreviewService

router = APIRouter()


def get_preview_service(db: Session = Depends(get_db)) -> PreviewService:
    return PreviewService(db)


@router.get("/{file_id}/thumbnail-url", name="request thumbnail url")
def request_thumbnail_url(
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    previews: PreviewService = Depends(get_preview_service),
):
    return success(data=previews.request_thumbnail_url(current_user, file_id))


@router.get("/{file_id}/preview-url", name="request preview url")
def request_preview_url(
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    previews: PreviewService = Depends(get_preview_service),
):
    return success(data=previews.request_preview_url(current_user, file_id))
