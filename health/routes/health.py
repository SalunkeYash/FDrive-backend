from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from dependencies.config import settings
from dependencies.response import success
from dependencies.sql_session import engine

router = APIRouter()


@router.get("/health", name="health")
def health():
    return success(data={"status": "ok", "service": "fdrive-api"})


@router.get("/ready", name="ready")
def ready():
    checks: dict[str, bool] = {"database": False}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False

    ok = all(checks.values())
    body = {
        "status": "ready" if ok else "not_ready",
        "environment": settings.environment,
        "checks": checks,
    }
    if ok:
        return success(data=body)
    return JSONResponse(
        content={"ok": False, "message": "not ready", "data": body},
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )
