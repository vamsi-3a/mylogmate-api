"""Admin service — platform-wide statistics and management operations.

All functions in this module require is_admin=True on the caller.
Enforcement happens at the route layer via Depends(get_admin_user).

Security:
  - Never expose passwords, tokens, or encrypted content.
  - All user-list results use UserAdminResponse (no password_hash).
  - Feedback content is plain text (voluntarily submitted — not encrypted).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ai_query_log import AIQueryLog
from app.db.models.feedback import Feedback
from app.db.models.log_entry import LogEntry
from app.db.models.user import User
from app.schemas.admin import (
    AdminStatsResponse,
    DailyCount,
    FeedbackAdminResponse,
    UserAdminResponse,
)

logger = structlog.get_logger()


# ── Stats ─────────────────────────────────────────────────────────────────


async def get_stats(db: AsyncSession) -> AdminStatsResponse:
    """Return platform-wide stats for the admin dashboard."""
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    thirty_days_ago = now - timedelta(days=30)

    # ── Scalar counts ─────────────────────────────────────────────────────
    total_users = (
        await db.execute(select(func.count()).select_from(User))
    ).scalar_one()

    active_users_last_30d = (
        await db.execute(
            select(func.count()).select_from(User).where(
                User.last_login_at >= thirty_days_ago
            )
        )
    ).scalar_one()

    total_log_entries = (
        await db.execute(
            select(func.count()).select_from(LogEntry).where(
                LogEntry.is_deleted.is_(False)
            )
        )
    ).scalar_one()

    total_ai_queries = (
        await db.execute(select(func.count()).select_from(AIQueryLog))
    ).scalar_one()

    ai_queries_today = (
        await db.execute(
            select(func.count()).select_from(AIQueryLog).where(
                AIQueryLog.created_at >= today_start
            )
        )
    ).scalar_one()

    unread_feedback_count = (
        await db.execute(
            select(func.count()).select_from(Feedback).where(
                Feedback.is_read.is_(False)
            )
        )
    ).scalar_one()

    # ── Time series: signups last 30 days ─────────────────────────────────
    signup_rows = (
        await db.execute(
            select(
                func.date(User.created_at).label("day"),
                func.count().label("cnt"),
            )
            .where(User.created_at >= thirty_days_ago)
            .group_by(func.date(User.created_at))
            .order_by(func.date(User.created_at))
        )
    ).all()
    signups_last_30d = [
        DailyCount(date=row[0], count=row[1]) for row in signup_rows
    ]

    # ── Time series: AI queries last 30 days ──────────────────────────────
    query_rows = (
        await db.execute(
            select(
                func.date(AIQueryLog.created_at).label("day"),
                func.count().label("cnt"),
            )
            .where(AIQueryLog.created_at >= thirty_days_ago)
            .group_by(func.date(AIQueryLog.created_at))
            .order_by(func.date(AIQueryLog.created_at))
        )
    ).all()
    ai_queries_last_30d = [
        DailyCount(date=row[0], count=row[1]) for row in query_rows
    ]

    return AdminStatsResponse(
        total_users=total_users,
        active_users_last_30d=active_users_last_30d,
        total_log_entries=total_log_entries,
        total_ai_queries=total_ai_queries,
        ai_queries_today=ai_queries_today,
        unread_feedback_count=unread_feedback_count,
        signups_last_30d=signups_last_30d,
        ai_queries_last_30d=ai_queries_last_30d,
    )


# ── Users ─────────────────────────────────────────────────────────────────


async def list_users(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 50,
    search: str | None = None,
) -> tuple[list[UserAdminResponse], int]:
    """Return paginated user list.

    Optionally filter by username/email prefix.
    Returns (items, total_count).
    """
    filters = []
    if search:
        pattern = f"%{search}%"
        filters.append(
            (User.username.ilike(pattern)) | (User.email.ilike(pattern))
        )

    where_clause = and_(*filters) if filters else None

    count_q = select(func.count()).select_from(User)
    if where_clause is not None:
        count_q = count_q.where(where_clause)
    total = (await db.execute(count_q)).scalar_one()

    offset = (page - 1) * page_size
    user_q = (
        select(User)
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    if where_clause is not None:
        user_q = user_q.where(where_clause)
    users = (await db.execute(user_q)).scalars().all()

    return [UserAdminResponse.model_validate(u) for u in users], total


async def toggle_user_active(
    db: AsyncSession,
    target_user_id: uuid.UUID,
) -> UserAdminResponse:
    """Toggle is_active for a user. Raises 404 if user not found.

    Admins cannot deactivate themselves via this endpoint (enforced at route).
    """
    from app.core.exceptions import NotFoundError

    result = await db.execute(select(User).where(User.id == target_user_id))
    user: User | None = result.scalar_one_or_none()
    if user is None:
        raise NotFoundError("User")

    user.is_active = not user.is_active
    await db.commit()
    await db.refresh(user)

    logger.info(
        "admin_user_toggled",
        user_id=str(target_user_id),
        is_active=user.is_active,
    )
    return UserAdminResponse.model_validate(user)


# ── Feedback ──────────────────────────────────────────────────────────────


async def list_feedback(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 50,
    unread_only: bool = False,
) -> tuple[list[FeedbackAdminResponse], int]:
    """Return paginated feedback list (newest first).

    Returns (items, total_count).
    """
    filters = []
    if unread_only:
        filters.append(Feedback.is_read.is_(False))

    where_clause = and_(*filters) if filters else None

    count_q = select(func.count()).select_from(Feedback)
    if where_clause is not None:
        count_q = count_q.where(where_clause)
    total = (await db.execute(count_q)).scalar_one()

    offset = (page - 1) * page_size
    fb_q = (
        select(Feedback, User.username)
        .join(User, Feedback.user_id == User.id)
        .order_by(Feedback.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    if where_clause is not None:
        fb_q = fb_q.where(where_clause)

    rows = (await db.execute(fb_q)).all()

    items = [
        FeedbackAdminResponse(
            id=fb.id,
            user_id=fb.user_id,
            username=username,
            content=fb.content,
            is_read=fb.is_read,
            created_at=fb.created_at,
        )
        for fb, username in rows
    ]
    return items, total


async def mark_feedback_read(
    db: AsyncSession,
    feedback_id: uuid.UUID,
) -> FeedbackAdminResponse:
    """Mark a feedback item as read. Raises 404 if not found."""
    from app.core.exceptions import NotFoundError

    result = await db.execute(
        select(Feedback, User.username)
        .join(User, Feedback.user_id == User.id)
        .where(Feedback.id == feedback_id)
    )
    row = result.first()
    if row is None:
        raise NotFoundError("Feedback")

    fb, username = row
    fb.is_read = True
    await db.commit()
    await db.refresh(fb)

    logger.info("admin_feedback_marked_read", feedback_id=str(feedback_id))
    return FeedbackAdminResponse(
        id=fb.id,
        user_id=fb.user_id,
        username=username,
        content=fb.content,
        is_read=fb.is_read,
        created_at=fb.created_at,
    )
