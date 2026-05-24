"""Admin-only response schemas.

These schemas are only returned to users where is_admin=True.
Never use these in user-facing endpoints.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

# ── Sub-schemas ────────────────────────────────────────────────────────────


class DailyCount(BaseModel):
    """Used for time-series analytics charts."""

    date: date
    count: int


# ── Response schemas ───────────────────────────────────────────────────────


class AdminStatsResponse(BaseModel):
    """Platform-wide statistics for the admin dashboard."""

    total_users: int
    active_users_last_30d: int
    total_log_entries: int
    total_ai_queries: int
    ai_queries_today: int
    unread_feedback_count: int
    # Signups per day for the past 30 days
    signups_last_30d: list[DailyCount]
    # AI queries per day for the past 30 days
    ai_queries_last_30d: list[DailyCount]


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

    model_config = ConfigDict(from_attributes=True)


class FeedbackAdminResponse(BaseModel):
    """Feedback record with submitting user info — admin view only."""

    id: uuid.UUID
    user_id: uuid.UUID
    username: str
    content: str
    is_read: bool
    created_at: datetime
