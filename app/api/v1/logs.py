"""Log entry routes.

All routes filter by the authenticated user — no cross-user access is possible.
Content is encrypted at the service layer; routes never touch raw plaintext.

Route order matters: /calendar/{year}/{month} MUST be declared before /{log_id}
so FastAPI matches the literal "calendar" segment before attempting UUID parsing.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.models.user import User
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.logs import (
    AssignTagsRequest,
    CalendarMonthResponse,
    CreateLogRequest,
    LogResponse,
    UpdateLogRequest,
)
from app.services import logs as logs_service

router = APIRouter(prefix="/logs", tags=["logs"])


# ── GET /logs ──────────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=PaginatedResponse[LogResponse],
    summary="List log entries for a context (paginated)",
)
async def list_logs(
    context_id: uuid.UUID,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    date_start: date | None = None,
    date_end: date | None = None,
    tag_ids: Annotated[list[uuid.UUID] | None, Query()] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[LogResponse]:
    items, total = await logs_service.list_logs(
        db,
        current_user,
        context_id=context_id,
        page=page,
        page_size=page_size,
        date_start=date_start,
        date_end=date_end,
        tag_ids=tag_ids,
    )
    return PaginatedResponse(
        data=items,
        total=total,
        page=page,
        page_size=page_size,
        message="Log entries retrieved",
    )


# ── POST /logs ─────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=ApiResponse[LogResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new log entry",
)
async def create_log(
    body: CreateLogRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[LogResponse]:
    entry = await logs_service.create_log(db, current_user, body)
    return ApiResponse(data=entry, message="Log entry created")


# ── GET /logs/calendar/{year}/{month} ─────────────────────────────────────
# IMPORTANT: must be declared BEFORE /{log_id} to avoid "calendar" being
# parsed as a log_id UUID (which would fail with 422).


@router.get(
    "/calendar/{year}/{month}",
    response_model=ApiResponse[CalendarMonthResponse],
    summary="Get log entry counts per day for a given month",
)
async def get_calendar(
    year: Annotated[int, Path(ge=2000, le=2100)],
    month: Annotated[int, Path(ge=1, le=12)],
    context_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[CalendarMonthResponse]:
    """Returns a CalendarMonthResponse with one entry per calendar day.

    Each day includes log_count (0 if no entries) and has_entries flag.
    Optionally filter by context_id (must belong to the current user).
    """
    cal = await logs_service.get_calendar(
        db, current_user, year, month, context_id=context_id
    )
    return ApiResponse(data=cal, message="Calendar retrieved")


# ── GET /logs/{log_id} ─────────────────────────────────────────────────────


@router.get(
    "/{log_id}",
    response_model=ApiResponse[LogResponse],
    summary="Get a single log entry",
)
async def get_log(
    log_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[LogResponse]:
    entry = await logs_service.get_log(db, log_id, current_user)
    return ApiResponse(data=entry, message="Log entry retrieved")


# ── PATCH /logs/{log_id} ───────────────────────────────────────────────────


@router.patch(
    "/{log_id}",
    response_model=ApiResponse[LogResponse],
    summary="Partially update a log entry",
)
async def update_log(
    log_id: uuid.UUID,
    body: UpdateLogRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[LogResponse]:
    entry = await logs_service.update_log(db, log_id, current_user, body)
    return ApiResponse(data=entry, message="Log entry updated")


# ── DELETE /logs/{log_id} ──────────────────────────────────────────────────


@router.delete(
    "/{log_id}",
    response_model=ApiResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Soft-delete a log entry",
)
async def delete_log(
    log_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    await logs_service.delete_log(db, log_id, current_user)
    return ApiResponse(data=None, message="Log entry deleted")


# ── PUT /logs/{log_id}/tags ────────────────────────────────────────────────


@router.put(
    "/{log_id}/tags",
    response_model=ApiResponse[LogResponse],
    summary="Replace all tags on a log entry",
)
async def assign_tags(
    log_id: uuid.UUID,
    body: AssignTagsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[LogResponse]:
    entry = await logs_service.assign_tags(db, log_id, current_user, body)
    return ApiResponse(data=entry, message="Tags updated")
