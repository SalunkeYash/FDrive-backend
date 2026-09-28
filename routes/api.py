from fastapi import APIRouter

from account.routes import router as account_router
from auth.routes import router as auth_router
from billing.routes import router as billing_router
from files.routes import router as files_router
from folders.routes import router as folders_router
from health.routes import router as health_router
from ops.routes import router as ops_router
from previews.routes import router as previews_router
from search.routes import router as search_router
from shares.routes import router as shares_router
from trash.routes import router as trash_router
from uploads.routes import router as uploads_router

router = APIRouter()
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(account_router)
router.include_router(folders_router)
router.include_router(files_router)
router.include_router(trash_router)
router.include_router(shares_router)
router.include_router(search_router)
router.include_router(previews_router)
router.include_router(uploads_router)
router.include_router(billing_router)
router.include_router(ops_router)
