"""Shared FastAPI dependencies injected into route handlers.

get_db           — yields an async DB session (per-request)
get_current_user — validates JWT Bearer token, returns authenticated User
get_admin_user   — get_current_user + asserts is_admin=True
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

import jwt
import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import AsyncSessionLocal

if TYPE_CHECKING:
    from app.db.models.user import User

logger = structlog.get_logger()

# HTTPBearer extracts `Authorization: Bearer <token>` header.
# auto_error=False lets us return a cleaner 401 ourselves.
_bearer_scheme = HTTPBearer(auto_error=False)


# ── Database session ──────────────────────────────────────────────────────


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async SQLAlchemy session; rollback on exception, always close."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Auth dependencies ─────────────────────────────────────────────────────


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate JWT access token and return the authenticated user.

    Raises 401 if:
    - Authorization header is missing or not Bearer
    - Token is expired, malformed, or wrong type
    - User no longer exists or is_active=False
    """
    from app.db.models.user import User

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not credentials:
        raise unauthorized

    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        user_id = uuid.UUID(str(payload["sub"]))
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError, KeyError):
        raise unauthorized from None

    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise unauthorized

    return user


async def get_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Return the current user only if they have is_admin=True.

    Raises 403 if the authenticated user is not an admin.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


# ── Context resolution ────────────────────────────────────────────────────


async def resolve_context_id(
    raw: str | uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> uuid.UUID:
    """Resolve a public-facing context_id into a real UUID.

    The frontend uses the magic string "self" to refer to the user's
    auto-created Self context without needing to know its UUID. This helper
    accepts that string OR a real UUID and returns the canonical UUID.

    Raises 400 if the value is neither "self" nor a valid UUID.
    Raises 404 if the user has no Self context (should never happen — created
    automatically at signup).
    """
    from app.db.models.context import Context

    if isinstance(raw, uuid.UUID):
        return raw

    if raw == "self":
        result = await db.execute(
            select(Context).where(
                Context.user_id == user_id,
                Context.type == "self",
            )
        )
        ctx = result.scalar_one_or_none()
        if ctx is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Self context not found for user",
            )
        return ctx.id

    try:
        return uuid.UUID(raw)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid context_id: {raw!r}",
        ) from None
