"""Shared FastAPI dependencies injected into route handlers.

get_db           — yields an async DB session (per-request)
get_current_user — validates JWT Bearer token, returns authenticated User
get_admin_user   — get_current_user + asserts is_admin=True

JWT + User model implementations are completed in Step 5 (Auth System).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

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


# ── Auth dependencies (fully implemented in Step 5) ───────────────────────


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate JWT access token and return the authenticated user.

    Raises 401 if token is missing, invalid, or expired.
    Raises 401 if user no longer exists or is_active=False.

    Full implementation added in Step 5.
    """
    # TODO: Step 5 — decode JWT, load User from DB, validate is_active
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication not yet implemented (Step 5)",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Return the current user only if they are an admin.

    Raises 403 if the authenticated user does not have is_admin=True.
    """
    # TODO: Step 5 — check current_user.is_admin
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access required",
    )
