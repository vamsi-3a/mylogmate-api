"""Admin API v1 routes — platform management (admin only).

All routes require is_admin=True via Depends(get_admin_user).

Routes:
  GET    /admin/stats                      — platform-wide statistics
  GET    /admin/users                      — paginated user list
  POST   /admin/users/{id}/toggle-active   — activate/deactivate user
  GET    /admin/feedback                   — paginated feedback list
  POST   /admin/feedback/{id}/mark-read    — mark feedback as read
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user, get_db
from app.db.models.user import User
from app.schemas.admin import (
    AdminDashboardResponse,
    FeedbackAdminResponse,
    UserAdminResponse,
)
from app.schemas.common import ApiResponse, PaginatedResponse
from app.services import admin as admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/stats",
    response_model=ApiResponse[AdminDashboardResponse],
    status_code=status.HTTP_200_OK,
)
async def get_stats(
    range: str = Query(
        "30d",
        pattern=r"^(7d|30d|90d|all)$",
        description="Time window for range-scoped metrics",
    ),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
) -> ApiResponse[AdminDashboardResponse]:
    """Return dashboard payload (stats + activity series + top users)."""
    dashboard = await admin_service.get_dashboard(db, range)
    return ApiResponse(data=dashboard, message="Dashboard retrieved")


@router.get(
    "/users",
    response_model=PaginatedResponse[UserAdminResponse],
    status_code=status.HTTP_200_OK,
)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str | None = Query(None, max_length=100),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
) -> PaginatedResponse[UserAdminResponse]:
    """Return paginated user list. Optionally filter by username/email."""
    items, total = await admin_service.list_users(
        db, page=page, page_size=page_size, search=search
    )
    return PaginatedResponse(
        data=items,
        total=total,
        page=page,
        page_size=page_size,
        message="Users retrieved",
    )


@router.post(
    "/users/{user_id}/toggle-active",
    response_model=ApiResponse[UserAdminResponse],
    status_code=status.HTTP_200_OK,
)
async def toggle_user_active(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> ApiResponse[UserAdminResponse]:
    """Toggle is_active for a user (activate or deactivate).

    Returns 400 if the admin tries to deactivate themselves.
    """
    from fastapi import HTTPException

    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot toggle your own account",
        )
    updated = await admin_service.toggle_user_active(db, user_id)
    action = "activated" if updated.is_active else "deactivated"
    return ApiResponse(data=updated, message=f"User {action}")


@router.get(
    "/feedback",
    response_model=PaginatedResponse[FeedbackAdminResponse],
    status_code=status.HTTP_200_OK,
)
async def list_feedback(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    unread_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
) -> PaginatedResponse[FeedbackAdminResponse]:
    """Return paginated feedback list. Use unread_only=true to filter."""
    items, total = await admin_service.list_feedback(
        db, page=page, page_size=page_size, unread_only=unread_only
    )
    return PaginatedResponse(
        data=items,
        total=total,
        page=page,
        page_size=page_size,
        message="Feedback retrieved",
    )


@router.post(
    "/feedback/{feedback_id}/mark-read",
    response_model=ApiResponse[FeedbackAdminResponse],
    status_code=status.HTTP_200_OK,
)
async def mark_feedback_read(
    feedback_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
) -> ApiResponse[FeedbackAdminResponse]:
    """Mark a feedback item as read."""
    fb = await admin_service.mark_feedback_read(db, feedback_id)
    return ApiResponse(data=fb, message="Feedback marked as read")
