from fastapi import APIRouter

from dependencies.metrics import snapshot
from dependencies.response import success

router = APIRouter()


@router.get("/metrics-snapshot", name="metrics snapshot")
def metrics_snapshot():
    return success(data=snapshot())
