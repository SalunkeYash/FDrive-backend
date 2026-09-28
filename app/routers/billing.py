from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.models import User
from app.schemas.billing import (
    CreateBillingPortalRequest,
    CreateBillingPortalResponse,
    CurrentPlanResponse,
    ListPlansResponse,
)
from app.services import billing as billing_service

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get(
    "/list-plans",
    response_model=ListPlansResponse,
    summary="List available storage plans",
)
def list_plans() -> ListPlansResponse:
    return billing_service.list_plans()


@router.get(
    "/current-plan",
    response_model=CurrentPlanResponse,
    summary="Show the signed-in user's current plan and usage",
)
def current_plan(current_user: User = Depends(get_current_user)) -> CurrentPlanResponse:
    return billing_service.current_plan(current_user)


@router.post(
    "/create-billing-portal-session",
    response_model=CreateBillingPortalResponse,
    summary="Start a billing portal session (Stripe stub until keys are configured)",
)
def create_billing_portal_session(
    body: CreateBillingPortalRequest,
    current_user: User = Depends(get_current_user),
) -> CreateBillingPortalResponse:
    return billing_service.create_billing_portal(current_user, body.return_url)
