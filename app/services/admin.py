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
    AdminDashboardResponse,
    AdminStats,
    FeedbackAdminResponse,
    TimeSeriesPoint,
    TopUser,
    UserAdminResponse,
)

logger = structlog.get_logger()


# ── Range helpers ─────────────────────────────────────────────────────────


def _range_to_days(range_key: str) -> int | None:
    """Translate the public ?range= param to a number of days.

    None means "all time" (no lower bound).
    """
    return {"7d": 7, "30d": 30, "90d": 90}.get(range_key)


# ── Stats ─────────────────────────────────────────────────────────────────


async def get_dashboard(db: AsyncSession, range_key: str) -> AdminDashboardResponse:
    """Build the full admin dashboard payload.

    Frontend expects: { stats, series, top_users }.
    All metrics are computed in a single round-trip per logical group.
    """
    now = datetime.now(UTC)
    period_days = _range_to_days(range_key)
    period_start = (
        now - timedelta(days=period_days) if period_days is not None else None
    )
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    # ── Headline counts ───────────────────────────────────────────────────
    total_users = (
        await db.execute(select(func.count()).select_from(User))
    ).scalar_one()

    active_7d = (
        await db.execute(
            select(func.count()).select_from(User).where(
                User.last_login_at >= seven_days_ago
            )
        )
    ).scalar_one()

    active_30d = (
        await db.execute(
            select(func.count()).select_from(User).where(
                User.last_login_at >= thirty_days_ago
            )
        )
    ).scalar_one()

    total_logs = (
        await db.execute(
            select(func.count()).select_from(LogEntry).where(
                LogEntry.is_deleted.is_(False)
            )
        )
    ).scalar_one()

    total_queries = (
        await db.execute(select(func.count()).select_from(AIQueryLog))
    ).scalar_one()

    # ── Range-scoped counts ───────────────────────────────────────────────
    if period_start is not None:
        new_signups_period = (
            await db.execute(
                select(func.count()).select_from(User).where(
                    User.created_at >= period_start
                )
            )
        ).scalar_one()

        ai_queries_period = (
            await db.execute(
                select(func.count()).select_from(AIQueryLog).where(
                    AIQueryLog.created_at >= period_start
                )
            )
        ).scalar_one()
    else:
        new_signups_period = total_users
        ai_queries_period = total_queries

    stats = AdminStats(
        total_users=total_users,
        active_users_7d=active_7d,
        active_users_30d=active_30d,
        total_logs=total_logs,
        total_ai_queries=total_queries,
        new_signups_period=new_signups_period,
        ai_queries_period=ai_queries_period,
    )

    # ── Time series (one point per day in window, fills gaps with zeros) ─
    series_window_days = period_days if period_days is not None else 30
    series = await _build_series(db, days=series_window_days, now=now)

    # ── Top loggers ───────────────────────────────────────────────────────
    top_rows = (
        await db.execute(
            select(User.username, func.count(LogEntry.id).label("cnt"))
            .join(LogEntry, LogEntry.user_id == User.id)
            .where(LogEntry.is_deleted.is_(False))
            .group_by(User.username)
            .order_by(func.count(LogEntry.id).desc())
            .limit(5)
        )
    ).all()
    top_users = [TopUser(username=row[0], count=row[1]) for row in top_rows]

    return AdminDashboardResponse(stats=stats, series=series, top_users=top_users)


async def _build_series(
    db: AsyncSession, days: int, now: datetime
) -> list[TimeSeriesPoint]:
    """Return one TimeSeriesPoint per day for the past `days` days.

    Gaps are filled with zeros so the chart x-axis is continuous.
    """
    start = (now - timedelta(days=days - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    signup_rows = (
        await db.execute(
            select(
                func.date(User.created_at).label("day"),
                func.count().label("cnt"),
            )
            .where(User.created_at >= start)
            .group_by(func.date(User.created_at))
        )
    ).all()
    signups_by_day = {row[0]: row[1] for row in signup_rows}

    query_rows = (
        await db.execute(
            select(
                func.date(AIQueryLog.created_at).label("day"),
                func.count().label("cnt"),
            )
            .where(AIQueryLog.created_at >= start)
            .group_by(func.date(AIQueryLog.created_at))
        )
    ).all()
    queries_by_day = {row[0]: row[1] for row in query_rows}

    series: list[TimeSeriesPoint] = []
    for i in range(days):
        day = (start + timedelta(days=i)).date()
        series.append(
            TimeSeriesPoint(
                date=day,
                signups=signups_by_day.get(day, 0),
                queries=queries_by_day.get(day, 0),
            )
        )
    return series


# ── Users ─────────────────────────────────────────────────────────────────


async def list_users(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 50,
    search: str | None = None,
) -> tuple[list[UserAdminResponse], int]:
    """Return paginated user list with per-user activity counts.

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
    users = list((await db.execute(user_q)).scalars().all())

    if not users:
        return [], total

    user_ids = [u.id for u in users]

    # Per-user log counts
    log_rows = (
        await db.execute(
            select(LogEntry.user_id, func.count().label("cnt"))
            .where(
                LogEntry.user_id.in_(user_ids),
                LogEntry.is_deleted.is_(False),
            )
            .group_by(LogEntry.user_id)
        )
    ).all()
    log_counts = {row[0]: row[1] for row in log_rows}

    # Per-user AI query counts
    query_rows = (
        await db.execute(
            select(AIQueryLog.user_id, func.count().label("cnt"))
            .where(AIQueryLog.user_id.in_(user_ids))
            .group_by(AIQueryLog.user_id)
        )
    ).all()
    query_counts = {row[0]: row[1] for row in query_rows}

    now = datetime.now(UTC)

    def _days_since_last_login(last: datetime | None) -> int:
        if last is None:
            return 9999
        delta = now - last
        return max(0, delta.days)

    items = [
        UserAdminResponse(
            id=u.id,
            username=u.username,
            email=u.email,
            auth_provider=u.auth_provider,
            is_admin=u.is_admin,
            is_active=u.is_active,
            last_login_at=u.last_login_at,
            created_at=u.created_at,
            updated_at=u.updated_at,
            log_count=log_counts.get(u.id, 0),
            query_count=query_counts.get(u.id, 0),
            last_active_days=_days_since_last_login(u.last_login_at),
        )
        for u in users
    ]
    return items, total


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

    # Refresh activity counts on the affected user (cheap — two scalar queries)
    log_count = (
        await db.execute(
            select(func.count()).select_from(LogEntry).where(
                LogEntry.user_id == user.id,
                LogEntry.is_deleted.is_(False),
            )
        )
    ).scalar_one()
    query_count = (
        await db.execute(
            select(func.count()).select_from(AIQueryLog).where(
                AIQueryLog.user_id == user.id
            )
        )
    ).scalar_one()
    now = datetime.now(UTC)
    last_active_days = (
        9999 if user.last_login_at is None
        else max(0, (now - user.last_login_at).days)
    )

    logger.info(
        "admin_user_toggled",
        user_id=str(target_user_id),
        is_active=user.is_active,
    )
    return UserAdminResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        auth_provider=user.auth_provider,
        is_admin=user.is_admin,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
        log_count=log_count,
        query_count=query_count,
        last_active_days=last_active_days,
    )


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
