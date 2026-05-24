"""Admin-only response schemas.

These schemas are only returned to users where is_admin=True.
Never use these in user-facing endpoints.

Shape mirrors the frontend's AdminDashboard / AdminUser / FeedbackItem types
so the React admin dashboard can render directly without remapping.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

# ── Sub-schemas ────────────────────────────────────────────────────────────


class TimeSeriesPoint(BaseModel):
    """One row in the activity-over-time chart."""

    date: date
    signups: int
    queries: int


class TopUser(BaseModel):
    """Leaderboard row for most active loggers."""

    username: str
    count: int


# ── Response schemas ───────────────────────────────────────────────────────


class AdminStats(BaseModel):
    """Headline counts for the admin dashboard cards."""

    total_users: int
    active_users_7d: int
    active_users_30d: int
    total_logs: int
    total_ai_queries: int
    # Counts within the selected range (7d/30d/90d/all)
    new_signups_period: int
    ai_queries_period: int


class AdminDashboardResponse(BaseModel):
    """Wraps the everything the admin dashboard needs in one call."""

    stats: AdminStats
    series: list[TimeSeriesPoint]
    top_users: list[TopUser]


class UserAdminResponse(BaseModel):
    """Extended user record visible to admins (includes activity fields)."""

    id: uuid.UUID
    username: str
    email: str | None
    auth_provider: str
    is_admin: bool
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime
    # Activity fields — computed by the admin service
    log_count: int = 0
    query_count: int = 0
    # Days since last_login_at; 0 == today, very large == never
    last_active_days: int = 9999

    model_config = ConfigDict(from_attributes=True)


class FeedbackAdminResponse(BaseModel):
    """Feedback record with submitting user info — admin view only."""

    id: uuid.UUID
    user_id: uuid.UUID
    username: str
    content: str
    is_read: bool
    created_at: datetime
