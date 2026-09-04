from sqlalchemy.orm import Session

from app.models import User
from app.schemas.users import StorageQuotaResponse
from app.services import quota
from app.services.users import update_display_name


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
