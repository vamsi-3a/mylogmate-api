"""ChatSession ORM model.

Represents a scoped AI recall conversation. Each session has:
  - A context (which Self/Teammate/Project the AI searched)
  - A time window (what date range was searched)
  - A title (auto-generated from the first user message)
  - Many ChatMessages (append-only)

context_id uses SET NULL on delete (not CASCADE) — we want to preserve
the chat history for reference even after the context is deleted. The
title and messages remain; the context reference becomes NULL.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.chat_message import ChatMessage
    from app.db.models.context import Context
    from app.db.models.user import User


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        # Chat history listing: most recent sessions first per user
        Index("ix_chat_sessions_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # SET NULL when context deleted — preserves chat history
    context_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contexts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Auto-populated from first user message (first 255 chars)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Recall filter settings captured at session creation
    time_window_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    time_window_end: Mapped[date | None] = mapped_column(Date, nullable=True)
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
    user: Mapped[User] = relationship("User", back_populates="chat_sessions")
    context: Mapped[Context | None] = relationship(
        "Context", back_populates="chat_sessions"
    )
    messages: Mapped[list[ChatMessage]] = relationship(
        "ChatMessage",
        back_populates="chat_session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )

    def __repr__(self) -> str:
        return f"<ChatSession id={self.id} title={self.title!r}>"
