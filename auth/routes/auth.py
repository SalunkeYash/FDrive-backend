from fastapi import APIRouter, Depends, Request, status

from auth.schemas.auth import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
)
from dependencies import metrics
from dependencies.authentication import get_auth_service
from dependencies.rate_limit import client_ip, enforce_auth_rate_limit
from dependencies.response import success
from service.audit_service import record_audit
from service.auth_service import AuthService

router = APIRouter()


@router.post("/register", name="register account")
def register_account(
    body: RegisterRequest,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
    enforce_auth_rate_limit(request)
    tokens = auth.register(body.email, body.password, body.display_name)
    record_audit(
        auth.db,
        action="auth.register",
        ip_address=client_ip(request),
        metadata={"email": body.email},
    )
    auth.db.commit()
    return success(data=tokens, message="account created", status_code=status.HTTP_201_CREATED)


@router.post("/login", name="login")
def login(
    body: LoginRequest,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
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
    return success(data=tokens)


@router.post("/refresh-token", name="refresh token")
def refresh_token(
    body: RefreshTokenRequest,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
    enforce_auth_rate_limit(request)
    tokens = auth.refresh(body.refresh_token)
    return success(data=tokens)


@router.post("/logout", name="logout")
def logout(
    body: RefreshTokenRequest,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
    auth.logout(body.refresh_token)
    record_audit(
        auth.db,
        action="auth.logout",
        ip_address=client_ip(request),
    )
    auth.db.commit()
    return success(message="logged out")
