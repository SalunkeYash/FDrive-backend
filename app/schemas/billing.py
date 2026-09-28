from pydantic import BaseModel, Field


class PlanInfo(BaseModel):
    plan_id: str
    name: str
    bytes_limit: int
    price_cents_monthly: int
    description: str


class ListPlansResponse(BaseModel):
    plans: list[PlanInfo]


class CurrentPlanResponse(BaseModel):
    plan_id: str
    name: str
    bytes_limit: int
    bytes_used: int


class CreateBillingPortalRequest(BaseModel):
    return_url: str = Field(min_length=1, max_length=2048)


class CreateBillingPortalResponse(BaseModel):
    portal_url: str
    status: str = Field(description="ready once Stripe is configured; otherwise stub")
