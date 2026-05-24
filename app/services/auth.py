"""Auth service — all authentication business logic.

Rules:
- NEVER log passwords, tokens, decrypted content.
- Every DB write is wrapped in a transaction (session.commit() on success).
- Google OAuth creates a user with auth_provider='google'; no password_hash stored.
- A 'Self' context is auto-created for every new user (local + google).
- Refresh token rotation: on each /refresh call, old token is invalidated
  and a new token+hash pair is stored.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_reset_token,
    decode_token,
    hash_password,
    hash_refresh_token,
    verify_google_token,
    verify_password,
)
from app.db.models.context import Context
from app.db.models.user import User
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
from app.workers.email_tasks import send_reset_password_email

logger = structlog.get_logger()


# ── Helpers ───────────────────────────────────────────────────────────────


def _build_token_response(user: User) -> tuple[TokenResponse, str]:
    """Create fresh access + refresh tokens for the given user.

    Returns (TokenResponse, raw_refresh_token).
    The caller is responsible for setting the refresh cookie and persisting
    user.refresh_token_hash.
    """
    access_token = create_access_token(
        user_id=str(user.id),
        username=user.username,
        is_admin=user.is_admin,
    )
    refresh_token = create_refresh_token(user_id=str(user.id))
    return (
        TokenResponse(
            access_token=access_token,
            user=UserResponse.model_validate(user),
        ),
        refresh_token,
    )


async def _create_self_context(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Create the default 'Self' context for a newly registered user."""
    context = Context(
        user_id=user_id,
        type="self",
        name="Self",
    )
    db.add(context)
    # Flush so the context ID is available if needed, but don't commit here —
    # the caller owns the transaction.
    await db.flush()


# ── Signup ────────────────────────────────────────────────────────────────


async def signup(db: AsyncSession, body: SignupRequest) -> tuple[TokenResponse, str]:
    """Register a new local user.

    Raises ConflictError if username or email already exists.
    Returns (TokenResponse, raw_refresh_token).
    """
    # Check uniqueness before attempting insert (gives a cleaner error message)
    existing = await db.execute(
        select(User).where(
            (User.username == body.username) | (User.email == body.email)
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError("Username or email already in use")

    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
        auth_provider="local",
        last_login_at=datetime.now(UTC),
    )
    db.add(user)
    await db.flush()  # user.id is now populated

    await _create_self_context(db, user.id)

    token_response, refresh_token = _build_token_response(user)
    user.refresh_token_hash = hash_refresh_token(refresh_token)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("Username or email already in use") from exc

    await db.refresh(user)
    logger.info("user_signup", user_id=str(user.id), auth_provider="local")

    token_response.user = UserResponse.model_validate(user)
    return token_response, refresh_token


# ── Login ─────────────────────────────────────────────────────────────────


async def login(db: AsyncSession, body: LoginRequest) -> tuple[TokenResponse, str]:
    """Authenticate a local user with username + password.

    Raises UnauthorizedError on bad credentials or inactive account.
    Returns (TokenResponse, raw_refresh_token).
    """
    result = await db.execute(select(User).where(User.username == body.username))
    user: User | None = result.scalar_one_or_none()

    if (
        user is None
        or user.auth_provider != "local"
        or user.password_hash is None
        or not verify_password(body.password, user.password_hash)
    ):
        raise UnauthorizedError("Invalid username or password")

    if not user.is_active:
        raise UnauthorizedError("Account is disabled")

    token_response, refresh_token = _build_token_response(user)
    user.refresh_token_hash = hash_refresh_token(refresh_token)
    user.last_login_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(user)

    logger.info("user_login", user_id=str(user.id))
    token_response.user = UserResponse.model_validate(user)
    return token_response, refresh_token


# ── Google OAuth ──────────────────────────────────────────────────────────


async def google_auth(
    db: AsyncSession, body: GoogleAuthRequest
) -> tuple[TokenResponse, str]:
    """Sign in or register via Google OAuth ID token.

    - If google_id already exists → login (update last_login_at).
    - If email matches a local account → link google_id to that account.
    - Otherwise → create new user with auth_provider='google'.

    Returns (TokenResponse, raw_refresh_token).
    """
    try:
        claims: dict[str, Any] = await verify_google_token(body.id_token)
    except ValueError as exc:
        raise UnauthorizedError(str(exc)) from exc

    google_id: str = str(claims["sub"])
    email: str = str(claims.get("email", ""))
    name: str = str(claims.get("name", ""))

    # 1. Existing Google user
    result = await db.execute(select(User).where(User.google_id == google_id))
    user: User | None = result.scalar_one_or_none()

    if user is None and email:
        # 2. Email matches existing local user → link
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            user.google_id = google_id
            user.auth_provider = "google"

    if user is None:
        # 3. New user — derive username from name/email
        base_username = _derive_username(name or email)
        username = await _unique_username(db, base_username)
        user = User(
            username=username,
            email=email or None,
            google_id=google_id,
            auth_provider="google",
        )
        db.add(user)
        await db.flush()
        await _create_self_context(db, user.id)

    if not user.is_active:
        raise UnauthorizedError("Account is disabled")

    token_response, refresh_token = _build_token_response(user)
    user.refresh_token_hash = hash_refresh_token(refresh_token)
    user.last_login_at = datetime.now(UTC)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("Account conflict — please try again") from exc

    await db.refresh(user)
    logger.info("user_google_auth", user_id=str(user.id))
    token_response.user = UserResponse.model_validate(user)
    return token_response, refresh_token


def _derive_username(source: str) -> str:
    """Derive a base username from a display name or email."""
    import re

    # Use the local part of email or the first word of display name
    if "@" in source:
        source = source.split("@")[0]
    else:
        source = source.split()[0] if source.split() else "user"
    # Strip non-alphanumeric/underscore chars, truncate
    base = re.sub(r"[^a-zA-Z0-9_]", "", source)[:40] or "user"
    return base


async def _unique_username(db: AsyncSession, base: str) -> str:
    """Return base if available, otherwise base_<suffix> with a collision counter."""
    for suffix in ["", *[str(i) for i in range(1, 100)]]:
        candidate = f"{base}{suffix}" if suffix else base
        if len(candidate) < 3:
            candidate = candidate + "usr"
        result = await db.execute(select(User).where(User.username == candidate))
        if result.scalar_one_or_none() is None:
            return candidate
    # Fallback: use a uuid fragment
    return f"user_{uuid.uuid4().hex[:8]}"


# ── Token refresh ─────────────────────────────────────────────────────────


async def refresh_tokens(
    db: AsyncSession, raw_refresh_token: str
) -> tuple[TokenResponse, str]:
    """Rotate the refresh token and issue a new access token.

    Validates:
    - JWT signature and expiry
    - Token type == 'refresh'
    - Stored hash matches (prevents replay of revoked tokens)
    - User still active

    Returns (TokenResponse, new_raw_refresh_token).
    """
    import jwt as _jwt

    try:
        payload = decode_token(raw_refresh_token, expected_type="refresh")
        user_id = uuid.UUID(str(payload["sub"]))
    except (_jwt.ExpiredSignatureError, _jwt.InvalidTokenError, ValueError, KeyError) as exc:
        raise UnauthorizedError("Invalid or expired refresh token") from exc

    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise UnauthorizedError("Invalid or expired refresh token")

    # Verify token hasn't been revoked (hash must match stored value)
    if user.refresh_token_hash != hash_refresh_token(raw_refresh_token):
        raise UnauthorizedError("Refresh token has been revoked")

    token_response, new_refresh_token = _build_token_response(user)
    user.refresh_token_hash = hash_refresh_token(new_refresh_token)

    await db.commit()
    await db.refresh(user)

    token_response.user = UserResponse.model_validate(user)
    return token_response, new_refresh_token


# ── Logout ────────────────────────────────────────────────────────────────


async def logout(db: AsyncSession, user: User) -> None:
    """Invalidate the user's refresh token (server-side revocation).

    The client must also clear the httpOnly cookie.
    """
    user.refresh_token_hash = None
    await db.commit()
    logger.info("user_logout", user_id=str(user.id))


# ── Password reset ────────────────────────────────────────────────────────


async def forgot_password(db: AsyncSession, body: ForgotPasswordRequest) -> str | None:
    """Generate a password reset token for the email address, if it exists.

    Returns the raw reset JWT (caller must email it), or None if no account found.
    We do NOT reveal whether the email exists (always respond 200 in the route).
    """
    result = await db.execute(
        select(User).where(User.email == body.email, User.auth_provider == "local")
    )
    user: User | None = result.scalar_one_or_none()
    if user is None:
        return None

    reset_token = create_reset_token(user_id=str(user.id))
    logger.info("password_reset_requested", user_id=str(user.id))
    # Dispatch email task — never log the token itself
    send_reset_password_email.delay(user.email, reset_token)
    return reset_token


async def reset_password(db: AsyncSession, body: ResetPasswordRequest) -> None:
    """Apply a password reset using the JWT reset token.

    Raises UnauthorizedError if the token is invalid/expired.
    Raises NotFoundError if the user no longer exists.
    """
    import jwt as _jwt

    try:
        payload = decode_token(body.token, expected_type="reset")
        user_id = uuid.UUID(str(payload["sub"]))
    except (_jwt.ExpiredSignatureError, _jwt.InvalidTokenError, ValueError, KeyError) as exc:
        raise UnauthorizedError("Invalid or expired reset token") from exc

    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()

    if user is None:
        raise NotFoundError("User not found")

    user.password_hash = hash_password(body.new_password)
    # Invalidate any active sessions after password reset
    user.refresh_token_hash = None

    await db.commit()
    logger.info("password_reset_completed", user_id=str(user.id))


# ── Profile update ────────────────────────────────────────────────────────


async def update_profile(
    db: AsyncSession, user: User, body: UpdateProfileRequest
) -> UserResponse:
    """Update username and/or email for the current user.

    Raises ConflictError if new username/email is already taken.
    """
    if body.username is not None:
        existing = await db.execute(
            select(User).where(User.username == body.username, User.id != user.id)
        )
        if existing.scalar_one_or_none():
            raise ConflictError("Username already taken")
        user.username = body.username

    if body.email is not None:
        existing = await db.execute(
            select(User).where(User.email == str(body.email), User.id != user.id)
        )
        if existing.scalar_one_or_none():
            raise ConflictError("Email already in use")
        user.email = str(body.email)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("Username or email already in use") from exc

    await db.refresh(user)
    return UserResponse.model_validate(user)


async def update_password(
    db: AsyncSession, user: User, body: UpdatePasswordRequest
) -> None:
    """Change password for a local auth user.

    Raises ValidationError if current_password is wrong.
    Raises ValidationError if auth_provider != 'local'.
    """
    if user.auth_provider != "local":
        raise ValidationError("Password change is only available for local accounts")

    if user.password_hash is None or not verify_password(
        body.current_password, user.password_hash
    ):
        raise ValidationError("Current password is incorrect")

    user.password_hash = hash_password(body.new_password)
    # Revoke all sessions on password change
    user.refresh_token_hash = None

    await db.commit()
    logger.info("password_changed", user_id=str(user.id))
