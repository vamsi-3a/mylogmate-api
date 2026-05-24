"""Context ORM model.

Three types: 'self' (auto-created at signup), 'teammate', 'project'.
The 'self' context is protected at application layer — cannot be deleted or renamed.

Cascade: deleting a context hard-deletes all its log_entries (ON DELETE CASCADE at DB level).
chat_sessions and ai_query_logs keep context_id as NULL when the context is deleted.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.ai_query_log import AIQueryLog
    from app.db.models.chat_session import ChatSession
    from app.db.models.log_entry import LogEntry
    from app.db.models.user import User


class Context(Base):
    __tablename__ = "contexts"
    __table_args__ = (
        # Prevent duplicate context names of the same type per user
        UniqueConstraint("user_id", "type", "name", name="uq_contexts_user_type_name"),
        Index("ix_contexts_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 'self' | 'teammate' | 'project'
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
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
    user: Mapped[User] = relationship("User", back_populates="contexts")
    log_entries: Mapped[list[LogEntry]] = relationship(
        "LogEntry", back_populates="context", cascade="all, delete-orphan"
    )
    # SET NULL on context delete — preserve chat history even after context removal
    chat_sessions: Mapped[list[ChatSession]] = relationship(
        "ChatSession", back_populates="context"
    )
    ai_query_logs: Mapped[list[AIQueryLog]] = relationship(
        "AIQueryLog", back_populates="context"
    )

    def __repr__(self) -> str:
        return f"<Context id={self.id} type={self.type!r} name={self.name!r}>"
