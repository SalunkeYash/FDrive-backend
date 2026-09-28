from fastapi import APIRouter

from auth.routes import auth

router = APIRouter()
router.include_router(auth.router, prefix="/auth", tags=["auth"])
