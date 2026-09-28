from fastapi import APIRouter

from app.core.metrics import snapshot

router = APIRouter(tags=["ops"])


@router.get("/metrics-snapshot", summary="Process-local counters for debugging")
def metrics_snapshot() -> dict[str, int]:
    return snapshot()
