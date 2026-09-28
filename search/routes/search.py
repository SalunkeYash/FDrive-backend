from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from dependencies.authentication import get_current_user
from dependencies.response import success
from dependencies.sql_session import get_db
from models import User
from service.search_service import SearchService

router = APIRouter()


def get_search_service(db: Session = Depends(get_db)) -> SearchService:
    return SearchService(db)


@router.get("", name="search drive")
def search_drive(
    q: str = Query(min_length=1, max_length=200),
    current_user: User = Depends(get_current_user),
    search: SearchService = Depends(get_search_service),
):
    return success(data=search.search_drive(current_user, q))
