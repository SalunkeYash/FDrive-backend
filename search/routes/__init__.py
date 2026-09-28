from fastapi import APIRouter

from search.routes import search

router = APIRouter()
router.include_router(search.router, prefix="/search", tags=["search"])
