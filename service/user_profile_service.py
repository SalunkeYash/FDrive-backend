from sqlalchemy.orm import Session

from models import User
from account.schemas.users import StorageQuotaResponse
from service import quota_service as quota
from model_handler.user_model_handler import update_display_name


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_storage_quota(self, user: User) -> StorageQuotaResponse:
        return StorageQuotaResponse(
            bytes_used=user.bytes_used,
            bytes_limit=user.bytes_limit,
            bytes_remaining=quota.bytes_remaining(user),
            usage_percent=quota.usage_percent(user),
        )

    def update_profile(self, user: User, display_name: str | None) -> User:
        update_display_name(user, display_name)
        self.db.commit()
        self.db.refresh(user)
        return user
