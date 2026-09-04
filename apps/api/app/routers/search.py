from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.search import SearchDriveResponse
from app.services.search import SearchService

router = APIRouter(prefix="/search", tags=["search"])


def get_search_service(db: Session = Depends(get_db)) -> SearchService:
    return SearchService(db)


@router.get(
    "/search-drive",
    response_model=SearchDriveResponse,
    summary="Search files and folders by name",
)
def search_drive(
    q: str = Query(min_length=1, max_length=200),
    current_user: User = Depends(get_current_user),
    search: SearchService = Depends(get_search_service),
) -> SearchDriveResponse:
    return search.search_drive(current_user, q)
