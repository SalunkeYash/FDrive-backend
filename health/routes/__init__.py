from fastapi import APIRouter

from health.routes import health

router = APIRouter()
router.include_router(health.router, tags=["health"])
