"""Authentication routes."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, UserSvc
from app.core.exceptions import AuthenticationError
from app.core.security import create_access_token, create_refresh_token, verify_token
from app.schemas.token import RefreshTokenRequest, Token
from app.schemas.user import UserCreate, UserRead

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    user_service: UserSvc,
) -> Any:
    """OAuth2 compatible token login.

    Returns access token and refresh token.
    Raises domain exceptions handled by exception handlers.
    """
    user = await user_service.authenticate(form_data.username, form_data.password)
    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token(subject=str(user.id))
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate,
    user_service: UserSvc,
) -> Any:
    """Register a new user.

    Raises AlreadyExistsError if email is already registered.
    """
    user = await user_service.register(user_in)
    return user


@router.post("/refresh", response_model=Token)
async def refresh_token(
    body: RefreshTokenRequest,
    user_service: UserSvc,
) -> Any:
    """Get new access token using refresh token.

    Raises AuthenticationError if refresh token is invalid or expired.
    """

    payload = verify_token(body.refresh_token)
    if payload is None:
        raise AuthenticationError(message="Invalid or expired refresh token")

    if payload.get("type") != "refresh":
        raise AuthenticationError(message="Invalid token type")

    user_id = payload.get("sub")
    if user_id is None:
        raise AuthenticationError(message="Invalid token payload")

    # Verify user still exists and is active
    user = await user_service.get_by_id(UUID(user_id))
    if not user.is_active:
        raise AuthenticationError(message="User account is disabled")

    access_token = create_access_token(subject=str(user.id))
    new_refresh_token = create_refresh_token(subject=str(user.id))
    return Token(access_token=access_token, refresh_token=new_refresh_token)


@router.get("/me", response_model=UserRead)
async def get_current_user_info(current_user: CurrentUser) -> Any:
    """Get current authenticated user information."""
    return current_user
