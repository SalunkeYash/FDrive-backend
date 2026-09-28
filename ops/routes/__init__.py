from fastapi import APIRouter

from ops.routes import ops

router = APIRouter()
router.include_router(ops.router, prefix="/ops", tags=["ops"])
