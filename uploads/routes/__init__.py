from fastapi import APIRouter

from uploads.routes import uploads

router = APIRouter()
router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
