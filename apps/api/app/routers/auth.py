from fastapi import APIRouter, Depends, Response, status

from app.core.deps import get_auth_service, get_current_user
from app.models import User
from app.schemas.auth import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    auth: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    return auth.register(body.email, body.password, body.display_name)


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    auth: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    return auth.login(body.email, body.password)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    body: RefreshTokenRequest,
    auth: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    return auth.refresh(body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    body: RefreshTokenRequest,
    auth: AuthService = Depends(get_auth_service),
) -> Response:
    auth.logout(body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
