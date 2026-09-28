from __future__ import annotations

from dependencies.config import settings
from models import User
from billing.schemas.billing import (
    CreateBillingPortalResponse,
    CurrentPlanResponse,
    ListPlansResponse,
    PlanInfo,
)

PLANS: list[PlanInfo] = [
    PlanInfo(
        plan_id="free",
        name="Free",
        bytes_limit=5 * 1024 * 1024 * 1024,
        price_cents_monthly=0,
        description="Personal starter quota",
    ),
    PlanInfo(
        plan_id="plus",
        name="Plus",
        bytes_limit=100 * 1024 * 1024 * 1024,
        price_cents_monthly=999,
        description="More space for active projects",
    ),
    PlanInfo(
        plan_id="pro",
        name="Pro",
        bytes_limit=1024 * 1024 * 1024 * 1024,
        price_cents_monthly=2499,
        description="Large libraries and teams later",
    ),
]


def list_plans() -> ListPlansResponse:
    return ListPlansResponse(plans=PLANS)


def current_plan(user: User) -> CurrentPlanResponse:
    matched = next((p for p in PLANS if p.bytes_limit == user.bytes_limit), PLANS[0])
    # Prefer free/plus/pro by limit proximity
    for plan in PLANS:
        if user.bytes_limit <= plan.bytes_limit:
            matched = plan
            break
    return CurrentPlanResponse(
        plan_id=matched.plan_id,
        name=matched.name,
        bytes_limit=user.bytes_limit,
        bytes_used=user.bytes_used,
    )


def create_billing_portal(user: User, return_url: str) -> CreateBillingPortalResponse:
    # Stripe Customer Portal lands in a later hardening pass when STRIPE_SECRET_KEY is set.
    if not getattr(settings, "stripe_secret_key", None):
        return CreateBillingPortalResponse(
            portal_url=return_url,
            status="stub",
        )
    return CreateBillingPortalResponse(
        portal_url=return_url,
        status="stub",
    )
