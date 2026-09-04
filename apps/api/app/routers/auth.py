from fastapi import APIRouter, Depends, Request, Response, status

from app.core import metrics
from app.core.deps import get_auth_service
from app.core.rate_limit import client_ip, enforce_auth_rate_limit
from app.schemas.auth import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
)
from app.services.audit import record_audit
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register-account",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new FDrive account",
)
def register_account(
    body: RegisterRequest,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    enforce_auth_rate_limit(request)
    tokens = auth.register(body.email, body.password, body.display_name)
    record_audit(
        auth.db,
        action="auth.register",
        ip_address=client_ip(request),
        metadata={"email": body.email},
    )
    auth.db.commit()
    return tokens


@router.post("/login", response_model=TokenResponse, summary="Sign in and get tokens")
def login(
    body: LoginRequest,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    enforce_auth_rate_limit(request)
    tokens = auth.login(body.email, body.password)
    metrics.incr("auth.login.success")
    record_audit(
        auth.db,
        action="auth.login",
        ip_address=client_ip(request),
        metadata={"email": body.email},
    )
    auth.db.commit()
    return tokens


@router.post(
    "/refresh-token",
    response_model=TokenResponse,
    summary="Exchange a refresh token for a new access token",
)
def refresh_token(
    body: RefreshTokenRequest,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    enforce_auth_rate_limit(request)
    return auth.refresh(body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke refresh token")
def logout(
    body: RefreshTokenRequest,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
) -> Response:
    auth.logout(body.refresh_token)
    record_audit(
        auth.db,
        action="auth.logout",
        ip_address=client_ip(request),
    )
    auth.db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
