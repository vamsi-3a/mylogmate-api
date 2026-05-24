"""User ORM model.

Supports two auth providers: 'local' (email + password) and 'google' (OAuth).
refresh_token_hash stores a SHA-256 hash of the current valid refresh token —
NULL means no active session. Cleared on logout, rotated on token refresh.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.ai_query_log import AIQueryLog
    from app.db.models.chat_session import ChatSession
    from app.db.models.context import Context
    from app.db.models.feedback import Feedback
    from app.db.models.log_entry import LogEntry
    from app.db.models.tag import Tag
    from app.db.models.template import Template


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_is_active", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    google_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    # 'local' | 'google'
    auth_provider: Mapped[str] = mapped_column(String(20), default="local")
    # SHA-256 hash of the current valid refresh token; NULL = no active session
    refresh_token_hash: Mapped[str | None] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Updated on every login — used by admin "active users" metric
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # ── Relationships ─────────────────────────────────────────────────────
    contexts: Mapped[list[Context]] = relationship(
        "Context", back_populates="user", cascade="all, delete-orphan"
    )
    log_entries: Mapped[list[LogEntry]] = relationship(
        "LogEntry", back_populates="user", cascade="all, delete-orphan"
    )
    tags: Mapped[list[Tag]] = relationship(
        "Tag", back_populates="user", cascade="all, delete-orphan"
    )
    templates: Mapped[list[Template]] = relationship(
        "Template", back_populates="user", cascade="all, delete-orphan"
    )
    chat_sessions: Mapped[list[ChatSession]] = relationship(
        "ChatSession", back_populates="user", cascade="all, delete-orphan"
    )
    feedback_items: Mapped[list[Feedback]] = relationship(
        "Feedback", back_populates="user", cascade="all, delete-orphan"
    )
    ai_query_logs: Mapped[list[AIQueryLog]] = relationship(
        "AIQueryLog", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"
