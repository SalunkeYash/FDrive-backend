from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.shares import (
    CreateLinkShareRequest,
    CreateUserShareRequest,
    SharedLinkAccessResponse,
    ShareResponse,
    SharedWithMeItem,
)
from app.services.shares import ShareService

router = APIRouter(prefix="/shares", tags=["shares"])


def get_share_service(db: Session = Depends(get_db)) -> ShareService:
    return ShareService(db)


@router.post(
    "/create-user-share",
    response_model=ShareResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Share a file or folder with another user by email",
)
def create_user_share(
    body: CreateUserShareRequest,
    current_user: User = Depends(get_current_user),
    shares: ShareService = Depends(get_share_service),
) -> ShareResponse:
    share = shares.create_user_share(
        current_user,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        grantee_email=body.grantee_email,
        role=body.role,
    )
    return ShareResponse.model_validate(share)


@router.post(
    "/create-link-share",
    response_model=ShareResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a public link share for a file or folder",
)
def create_link_share(
    body: CreateLinkShareRequest,
    current_user: User = Depends(get_current_user),
    shares: ShareService = Depends(get_share_service),
) -> ShareResponse:
    share = shares.create_link_share(
        current_user,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        role=body.role,
    )
    return ShareResponse.model_validate(share)


@router.get(
    "/list-my-shares",
    response_model=list[ShareResponse],
    summary="List shares you created",
)
def list_my_shares(
    current_user: User = Depends(get_current_user),
    shares: ShareService = Depends(get_share_service),
) -> list[ShareResponse]:
    return shares.list_my_shares(current_user)


@router.get(
    "/list-shared-with-me",
    response_model=list[SharedWithMeItem],
    summary="List items shared with you",
)
def list_shared_with_me(
    current_user: User = Depends(get_current_user),
    shares: ShareService = Depends(get_share_service),
) -> list[SharedWithMeItem]:
    return shares.list_shared_with_me(current_user)


@router.post(
    "/{share_id}/revoke-share",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a share you own",
)
def revoke_share(
    share_id: UUID,
    current_user: User = Depends(get_current_user),
    shares: ShareService = Depends(get_share_service),
) -> Response:
    shares.revoke_share(current_user, share_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/access-shared-link/{token}",
    response_model=SharedLinkAccessResponse,
    summary="Open a shared link by token (no login required)",
)
def access_shared_link(
    token: str,
    shares: ShareService = Depends(get_share_service),
) -> SharedLinkAccessResponse:
    return shares.access_shared_link(token)
