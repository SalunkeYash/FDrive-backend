from fastapi import APIRouter

from shares.routes import shares

router = APIRouter()
router.include_router(shares.router, prefix="/shares", tags=["shares"])
