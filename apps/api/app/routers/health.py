from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe — process is up."""
    return {"status": "ok", "service": "fdrive-api"}


@router.get("/ready")
def ready() -> dict[str, str | bool]:
    """Readiness probe — expand with DB/Redis checks in later phases."""
    return {
        "status": "ready",
        "environment": settings.environment,
        "checks": True,
    }
