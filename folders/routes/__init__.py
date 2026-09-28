from fastapi import APIRouter

from folders.routes import folders

router = APIRouter()
router.include_router(folders.router, prefix="/folders", tags=["folders"])
