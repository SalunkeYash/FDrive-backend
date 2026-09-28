from fastapi import APIRouter

from files.routes import files

router = APIRouter()
router.include_router(files.router, prefix="/files", tags=["files"])
