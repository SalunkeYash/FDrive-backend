from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from dependencies.authentication import get_current_user, get_optional_user
from dependencies.response import success
from dependencies.sql_session import get_db
from models import User
from shares.schemas.shares import (
    CreateLinkShareRequest,
    CreateUserShareRequest,
    RequestAccessRequest,
    SetLinkAccessRequest,
    ShareResponse,
)
from service.share_service import ShareService

router = APIRouter()


def get_share_service(db: Session = Depends(get_db)) -> ShareService:
    return ShareService(db)


@router.post("/user", name="create user share")
def create_user_share(
    body: CreateUserShareRequest,
    current_user: User = Depends(get_current_user),
    shares: ShareService = Depends(get_share_service),
):
    share = shares.create_user_share(
        current_user,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        grantee_email=body.grantee_email,
        role=body.role,
    )
    return success(
        data=ShareResponse.model_validate(share),
        message="share created",
        status_code=status.HTTP_201_CREATED,
    )


@router.post("/link", name="create link share")
def create_link_share(
    body: CreateLinkShareRequest,
    current_user: User = Depends(get_current_user),
    shares: ShareService = Depends(get_share_service),
):
    share = shares.create_link_share(
        current_user,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        role=body.role,
    )
    return success(
        data=ShareResponse.model_validate(share),
        message="link share created",
        status_code=status.HTTP_201_CREATED,
    )


@router.post("/link-access", name="set link access")
def set_link_access(
    body: SetLinkAccessRequest,
    current_user: User = Depends(get_current_user),
    shares: ShareService = Depends(get_share_service),
):
    shares.set_link_access(
        current_user,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        access=body.access,
        role=body.role,
    )
    data = shares.get_resource_access(
        current_user,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
    )
    return success(data=data)


@router.get("/resource-access", name="list resource access")
def list_resource_access(
    resource_type: str = Query(pattern="^(file|folder)$"),
    resource_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    shares: ShareService = Depends(get_share_service),
):
    return success(
        data=shares.get_resource_access(
            current_user,
            resource_type=resource_type,
            resource_id=resource_id,
        )
    )


@router.get("/resolve", name="resolve shared item")
def resolve_shared_item(
    resource_type: str = Query(pattern="^(file|folder)$"),
    resource_id: UUID = Query(...),
    current_user: User | None = Depends(get_optional_user),
    shares: ShareService = Depends(get_share_service),
):
    return success(
        data=shares.resolve_shared_item(
            resource_type=resource_type,
            resource_id=resource_id,
            user=current_user,
        )
    )


@router.post("/access-requests", name="request access")
def request_access(
    body: RequestAccessRequest,
    current_user: User = Depends(get_current_user),
    shares: ShareService = Depends(get_share_service),
):
    row = shares.request_access(
        current_user,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        role=body.role,
        message=body.message,
    )
    return success(
        data=shares._access_request_response(row),
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/access-requests", name="list access requests")
def list_access_requests(
    resource_type: str = Query(pattern="^(file|folder)$"),
    resource_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    shares: ShareService = Depends(get_share_service),
):
    return success(
        data=shares.list_access_requests_for_resource(
            current_user,
            resource_type=resource_type,
            resource_id=resource_id,
        )
    )


@router.post("/access-requests/{request_id}/approve", name="approve access request")
def approve_access_request(
    request_id: UUID,
    current_user: User = Depends(get_current_user),
    shares: ShareService = Depends(get_share_service),
):
    share = shares.approve_access_request(current_user, request_id)
    return success(data=ShareResponse.model_validate(share), message="access approved")


@router.post("/access-requests/{request_id}/deny", name="deny access request")
def deny_access_request(
    request_id: UUID,
    current_user: User = Depends(get_current_user),
    shares: ShareService = Depends(get_share_service),
):
    shares.deny_access_request(current_user, request_id)
    return success(message="access denied")


@router.get("/mine", name="list my shares")
def list_my_shares(
    current_user: User = Depends(get_current_user),
    shares: ShareService = Depends(get_share_service),
):
    return success(data=shares.list_my_shares(current_user))


@router.get("/shared-with-me", name="list shared with me")
def list_shared_with_me(
    current_user: User = Depends(get_current_user),
    shares: ShareService = Depends(get_share_service),
):
    return success(data=shares.list_shared_with_me(current_user))


@router.post("/{share_id}/revoke", name="revoke share")
def revoke_share(
    share_id: UUID,
    current_user: User = Depends(get_current_user),
    shares: ShareService = Depends(get_share_service),
):
    shares.revoke_share(current_user, share_id)
    return success(message="share revoked")


@router.get("/link/{token}", name="access shared link")
def access_shared_link(
    token: str,
    shares: ShareService = Depends(get_share_service),
):
    return success(data=shares.access_shared_link(token))


@router.get("/link/{token}/contents", name="list link contents")
def list_link_contents(
    token: str,
    folder_id: UUID | None = Query(default=None),
    shares: ShareService = Depends(get_share_service),
):
    return success(data=shares.list_link_contents(token, folder_id=folder_id))


@router.get("/link/{token}/files/{file_id}/download-url", name="link download url")
def link_download_url(
    token: str,
    file_id: UUID,
    shares: ShareService = Depends(get_share_service),
):
    return success(data=shares.request_link_download_url(token, file_id))


@router.get("/link/{token}/files/{file_id}/preview-url", name="link preview url")
def link_preview_url(
    token: str,
    file_id: UUID,
    shares: ShareService = Depends(get_share_service),
):
    return success(data=shares.request_link_preview_url(token, file_id))


@router.get("/link/{token}/files/{file_id}/thumbnail-url", name="link thumbnail url")
def link_thumbnail_url(
    token: str,
    file_id: UUID,
    shares: ShareService = Depends(get_share_service),
):
    return success(data=shares.request_link_thumbnail_url(token, file_id))
