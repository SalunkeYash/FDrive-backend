from fastapi import APIRouter, Depends

from billing.schemas.billing import CreateBillingPortalRequest
from dependencies.authentication import get_current_user
from dependencies.response import success
from models import User
from service import billing_service

router = APIRouter()


@router.get("/plans", name="list plans")
def list_plans():
    return success(data=billing_service.list_plans())


@router.get("/current-plan", name="current plan")
def current_plan(current_user: User = Depends(get_current_user)):
    return success(data=billing_service.current_plan(current_user))


@router.post("/portal-session", name="create billing portal session")
def create_billing_portal_session(
    body: CreateBillingPortalRequest,
    current_user: User = Depends(get_current_user),
):
    return success(
        data=billing_service.create_billing_portal(current_user, body.return_url)
    )
