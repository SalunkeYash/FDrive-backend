from fastapi import APIRouter

from account.routes import account

router = APIRouter()
router.include_router(account.router, prefix="/account", tags=["account"])
