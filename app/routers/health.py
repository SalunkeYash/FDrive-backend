from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe — process is up."""
    return {"status": "ok", "service": "fdrive-api"}


@router.get("/ready")
def ready() -> JSONResponse:
    """Readiness probe — verifies Postgres connectivity."""
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
    return JSONResponse(
        content=body,
        status_code=status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
