from fastapi import APIRouter, Depends, Response, status

from app.core.deps import get_auth_service
from app.schemas.auth import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
)
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
    auth: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    return auth.register(body.email, body.password, body.display_name)


@router.post("/login", response_model=TokenResponse, summary="Sign in and get tokens")
def login(
    body: LoginRequest,
    auth: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    return auth.login(body.email, body.password)


@router.post(
    "/refresh-token",
    response_model=TokenResponse,
    summary="Exchange a refresh token for a new access token",
)
def refresh_token(
    body: RefreshTokenRequest,
    auth: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    return auth.refresh(body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke refresh token")
def logout(
    body: RefreshTokenRequest,
    auth: AuthService = Depends(get_auth_service),
) -> Response:
    auth.logout(body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
