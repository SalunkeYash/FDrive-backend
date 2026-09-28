from fastapi import APIRouter

from trash.routes import trash

router = APIRouter()
router.include_router(trash.router, prefix="/trash", tags=["trash"])
