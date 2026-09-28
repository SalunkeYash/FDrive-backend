from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from account.schemas.users import StorageQuotaResponse, UpdateProfileRequest
from auth.schemas.auth import UserResponse
from dependencies.authentication import get_current_user
from dependencies.response import success
from dependencies.sql_session import get_db
from models import User
from service.user_profile_service import UserService

router = APIRouter()


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


@router.get("/profile", name="get profile")
def get_profile(current_user: User = Depends(get_current_user)):
    return success(data=UserResponse.model_validate(current_user))


@router.patch("/profile", name="update profile")
def update_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    users: UserService = Depends(get_user_service),
):
    user = users.update_profile(current_user, body.display_name)
    return success(data=UserResponse.model_validate(user), message="profile updated")


@router.get("/storage-quota", name="get storage quota")
def get_storage_quota(
    current_user: User = Depends(get_current_user),
    users: UserService = Depends(get_user_service),
):
    return success(data=users.get_storage_quota(current_user))
