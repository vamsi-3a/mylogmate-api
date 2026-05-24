"""AIQueryLog ORM model — audit log for AI recall queries.

Two purposes:
  1. Rate limiting: COUNT(*) WHERE user_id=? AND created_at >= today
     (index on user_id, created_at makes this O(log n))
  2. Admin analytics: query volume over time, latency monitoring

SECURITY: prompt_preview is at most 150 chars of the user's question.
NEVER store the full prompt — it may contain sensitive context.
context_id uses SET NULL on delete — preserves analytics after context removal.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.context import Context
    from app.db.models.user import User


class AIQueryLog(Base):
    __tablename__ = "ai_query_logs"
    __table_args__ = (
        # Rate limit check: COUNT(*) WHERE user_id=? AND created_at >= today
        Index("ix_ai_query_logs_user_created", "user_id", "created_at"),
        # Admin analytics: all queries ordered by time
        Index("ix_ai_query_logs_created_at", "created_at"),
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
    # SET NULL when context deleted — preserve analytics
    context_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contexts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Truncated to 150 chars — NEVER the full user prompt
    prompt_preview: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # End-to-end AI query latency in milliseconds
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Append-only — no updated_at
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    # ── Relationships ─────────────────────────────────────────────────────
    user: Mapped[User] = relationship("User", back_populates="ai_query_logs")
    context: Mapped[Context | None] = relationship(
        "Context", back_populates="ai_query_logs"
    )

    def __repr__(self) -> str:
        return f"<AIQueryLog id={self.id} tokens={self.tokens_used}>"
