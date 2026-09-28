from fastapi import APIRouter

from previews.routes import previews

router = APIRouter()
router.include_router(previews.router, prefix="/previews", tags=["previews"])
