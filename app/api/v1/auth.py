"""Auth routes — thin handlers that delegate all logic to app.services.auth.

Cookie name for refresh token: refresh_token
httpOnly=True, secure=True (secure=False in dev), samesite='lax'
"""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.rate_limit import limiter
from app.schemas.auth import (
    ForgotPasswordRequest,
    GoogleAuthRequest,
    LoginRequest,
    ResetPasswordRequest,
    SignupRequest,
    TokenResponse,
    UpdatePasswordRequest,
    UpdateProfileRequest,
    UserResponse,
)
from app.schemas.common import ApiResponse
from app.services import auth as auth_service

if True:  # TYPE_CHECKING would hide the import from the router
    from app.db.models.user import User

logger = structlog.get_logger()

router = APIRouter(prefix="/auth", tags=["auth"])

# Refresh cookie settings — matches the JWT_ALGORITHM choice
_COOKIE_NAME = "refresh_token"
_COOKIE_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86_400  # seconds
_COOKIE_SECURE = settings.APP_ENV != "development"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="lax",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_COOKIE_NAME, httponly=True, secure=_COOKIE_SECURE)


# ── POST /auth/signup ──────────────────────────────────────────────────────


@router.post(
    "/signup",
    response_model=ApiResponse[TokenResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new local user",
)
@limiter.limit(settings.AUTH_RATE_LIMIT)
async def signup(
    request: Request,
    body: SignupRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TokenResponse]:
    token_response, refresh_token = await auth_service.signup(db, body)
    _set_refresh_cookie(response, refresh_token)
    return ApiResponse(data=token_response, message="Account created successfully")


# ── POST /auth/login ───────────────────────────────────────────────────────


@router.post(
    "/login",
    response_model=ApiResponse[TokenResponse],
    summary="Login with username + password",
)
@limiter.limit(settings.AUTH_RATE_LIMIT)
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TokenResponse]:
    token_response, refresh_token = await auth_service.login(db, body)
    _set_refresh_cookie(response, refresh_token)
    return ApiResponse(data=token_response, message="Login successful")


# ── POST /auth/google ──────────────────────────────────────────────────────


@router.post(
    "/google",
    response_model=ApiResponse[TokenResponse],
    summary="Sign in or register via Google OAuth",
)
async def google_auth(
    body: GoogleAuthRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TokenResponse]:
    token_response, refresh_token = await auth_service.google_auth(db, body)
    _set_refresh_cookie(response, refresh_token)
    return ApiResponse(data=token_response, message="Google authentication successful")


# ── POST /auth/refresh ─────────────────────────────────────────────────────


@router.post(
    "/refresh",
    response_model=ApiResponse[TokenResponse],
    summary="Rotate refresh token and issue new access token",
)
async def refresh(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: Annotated[str | None, Cookie(alias=_COOKIE_NAME)] = None,
) -> ApiResponse[TokenResponse]:
    from app.core.exceptions import UnauthorizedError

    if not refresh_token:
        raise UnauthorizedError("No refresh token provided")

    token_response, new_refresh_token = await auth_service.refresh_tokens(db, refresh_token)
    _set_refresh_cookie(response, new_refresh_token)
    return ApiResponse(data=token_response, message="Token refreshed")


# ── POST /auth/logout ──────────────────────────────────────────────────────


@router.post(
    "/logout",
    response_model=ApiResponse[None],
    summary="Revoke refresh token and clear cookie",
)
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    await auth_service.logout(db, current_user)
    _clear_refresh_cookie(response)
    return ApiResponse(data=None, message="Logged out successfully")


# ── POST /auth/forgot-password ─────────────────────────────────────────────


@router.post(
    "/forgot-password",
    response_model=ApiResponse[None],
    summary="Request a password reset email",
)
@limiter.limit(settings.AUTH_RATE_LIMIT)
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    reset_token = await auth_service.forgot_password(db, body)

    if reset_token:
        # TODO Step 12: dispatch send_reset_email.delay(body.email, reset_token)
        logger.info("password_reset_email_queued", email=body.email)

    # Always return 200 — don't reveal whether email exists
    return ApiResponse(
        data=None,
        message="If that email is registered, a reset link has been sent",
    )


# ── POST /auth/reset-password ──────────────────────────────────────────────


@router.post(
    "/reset-password",
    response_model=ApiResponse[None],
    summary="Reset password using the emailed token",
)
@limiter.limit(settings.AUTH_RATE_LIMIT)
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    await auth_service.reset_password(db, body)
    return ApiResponse(data=None, message="Password reset successfully")


# ── GET /auth/me ───────────────────────────────────────────────────────────


@router.get(
    "/me",
    response_model=ApiResponse[UserResponse],
    summary="Get the current authenticated user",
)
async def me(
    current_user: User = Depends(get_current_user),
) -> ApiResponse[UserResponse]:
    return ApiResponse(
        data=UserResponse.model_validate(current_user),
        message="User profile retrieved",
    )


# ── PATCH /auth/me ─────────────────────────────────────────────────────────


@router.patch(
    "/me",
    response_model=ApiResponse[UserResponse],
    summary="Update username or email",
)
async def update_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UserResponse]:
    user_response = await auth_service.update_profile(db, current_user, body)
    return ApiResponse(data=user_response, message="Profile updated")


# ── POST /auth/me/password ─────────────────────────────────────────────────


@router.post(
    "/me/password",
    response_model=ApiResponse[None],
    summary="Change password (local accounts only)",
)
async def update_password(
    body: UpdatePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    await auth_service.update_password(db, current_user, body)
    return ApiResponse(data=None, message="Password changed successfully")
