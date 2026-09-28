from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.auth import UserResponse
from app.schemas.users import StorageQuotaResponse, UpdateProfileRequest
from app.services.user_profile import UserService

router = APIRouter(prefix="/account", tags=["account"])


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


@router.get(
    "/profile",
    response_model=UserResponse,
    summary="Get the signed-in user's profile",
)
def get_profile(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch(
    "/profile",
    response_model=UserResponse,
    summary="Update the signed-in user's profile",
)
def update_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    users: UserService = Depends(get_user_service),
) -> User:
    return users.update_profile(current_user, body.display_name)


@router.get(
    "/storage-quota",
    response_model=StorageQuotaResponse,
    summary="Get how much storage the user has used and how much remains",
)
def get_storage_quota(
    current_user: User = Depends(get_current_user),
    users: UserService = Depends(get_user_service),
) -> StorageQuotaResponse:
    return users.get_storage_quota(current_user)
