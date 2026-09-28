from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_optional_user
from app.db.session import get_db
from app.models import User
from app.schemas.files import RequestDownloadUrlResponse
from app.schemas.previews import PreviewUrlResponse
from app.schemas.shares import (
    AccessRequestResponse,
    CreateLinkShareRequest,
    CreateUserShareRequest,
    RequestAccessRequest,
    ResourceAccessResponse,
    ResolveSharedItemResponse,
    SetLinkAccessRequest,
    SharedLinkAccessResponse,
    SharedLinkContentsResponse,
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
    summary="Create or update a public link share for a file or folder",
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


@router.post(
    "/set-link-access",
    response_model=ResourceAccessResponse,
    summary="Set general access to restricted or anyone with the link",
)
def set_link_access(
    body: SetLinkAccessRequest,
    current_user: User = Depends(get_current_user),
    shares: ShareService = Depends(get_share_service),
) -> ResourceAccessResponse:
    shares.set_link_access(
        current_user,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        access=body.access,
        role=body.role,
    )
    return shares.get_resource_access(
        current_user,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
    )


@router.get(
    "/list-resource-access",
    response_model=ResourceAccessResponse,
    summary="List people and link access for a file or folder you own",
)
def list_resource_access(
    resource_type: str = Query(pattern="^(file|folder)$"),
    resource_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    shares: ShareService = Depends(get_share_service),
) -> ResourceAccessResponse:
    return shares.get_resource_access(
        current_user,
        resource_type=resource_type,
        resource_id=resource_id,
    )


@router.get(
    "/resolve-shared-item",
    response_model=ResolveSharedItemResponse,
    summary="Resolve a stable shared item link (public, allowed, or denied)",
)
def resolve_shared_item(
    resource_type: str = Query(pattern="^(file|folder)$"),
    resource_id: UUID = Query(...),
    current_user: User | None = Depends(get_optional_user),
    shares: ShareService = Depends(get_share_service),
) -> ResolveSharedItemResponse:
    return shares.resolve_shared_item(
        resource_type=resource_type,
        resource_id=resource_id,
        user=current_user,
    )


@router.post(
    "/request-access",
    response_model=AccessRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request access to a restricted file or folder",
)
def request_access(
    body: RequestAccessRequest,
    current_user: User = Depends(get_current_user),
    shares: ShareService = Depends(get_share_service),
) -> AccessRequestResponse:
    row = shares.request_access(
        current_user,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        role=body.role,
        message=body.message,
    )
    return shares._access_request_response(row)


@router.get(
    "/list-access-requests",
    response_model=list[AccessRequestResponse],
    summary="List pending access requests for a resource you own",
)
def list_access_requests(
    resource_type: str = Query(pattern="^(file|folder)$"),
    resource_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    shares: ShareService = Depends(get_share_service),
) -> list[AccessRequestResponse]:
    return shares.list_access_requests_for_resource(
        current_user,
        resource_type=resource_type,
        resource_id=resource_id,
    )


@router.post(
    "/access-requests/{request_id}/approve",
    response_model=ShareResponse,
    summary="Approve an access request and grant a user share",
)
def approve_access_request(
    request_id: UUID,
    current_user: User = Depends(get_current_user),
    shares: ShareService = Depends(get_share_service),
) -> ShareResponse:
    share = shares.approve_access_request(current_user, request_id)
    return ShareResponse.model_validate(share)


@router.post(
    "/access-requests/{request_id}/deny",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deny an access request",
)
def deny_access_request(
    request_id: UUID,
    current_user: User = Depends(get_current_user),
    shares: ShareService = Depends(get_share_service),
) -> Response:
    shares.deny_access_request(current_user, request_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


@router.get(
    "/link/{token}/contents",
    response_model=SharedLinkContentsResponse,
    summary="List folders and files visible through a share link",
)
def list_link_contents(
    token: str,
    folder_id: UUID | None = Query(default=None),
    shares: ShareService = Depends(get_share_service),
) -> SharedLinkContentsResponse:
    return shares.list_link_contents(token, folder_id=folder_id)


@router.get(
    "/link/{token}/files/{file_id}/download-url",
    response_model=RequestDownloadUrlResponse,
    summary="Presigned download URL for a file on a share link",
)
def link_download_url(
    token: str,
    file_id: UUID,
    shares: ShareService = Depends(get_share_service),
) -> RequestDownloadUrlResponse:
    return shares.request_link_download_url(token, file_id)


@router.get(
    "/link/{token}/files/{file_id}/preview-url",
    response_model=PreviewUrlResponse,
    summary="Presigned preview URL for a file on a share link",
)
def link_preview_url(
    token: str,
    file_id: UUID,
    shares: ShareService = Depends(get_share_service),
) -> PreviewUrlResponse:
    return shares.request_link_preview_url(token, file_id)


@router.get(
    "/link/{token}/files/{file_id}/thumbnail-url",
    response_model=PreviewUrlResponse,
    summary="Presigned thumbnail URL for a file on a share link",
)
def link_thumbnail_url(
    token: str,
    file_id: UUID,
    shares: ShareService = Depends(get_share_service),
) -> PreviewUrlResponse:
    return shares.request_link_thumbnail_url(token, file_id)
