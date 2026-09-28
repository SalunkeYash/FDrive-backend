from fastapi import APIRouter

from billing.routes import billing

router = APIRouter()
router.include_router(billing.router, prefix="/billing", tags=["billing"])
