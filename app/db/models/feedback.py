"""Feedback ORM model.

Stores voluntary user feedback submitted via the in-app feedback modal.
is_read is toggled by admins via the /api/v1/admin/feedback endpoint.
Feedback content is plain text (not encrypted) — it is voluntarily submitted
and intended to be read by the admin.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (
        Index("ix_feedback_created_at", "created_at"),
        Index("ix_feedback_is_read", "is_read"),
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
    # Plain text — voluntarily submitted, admin-facing
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Admin marks as reviewed
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Append-only — no updated_at
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    # ── Relationships ─────────────────────────────────────────────────────
    user: Mapped[User] = relationship("User", back_populates="feedback_items")

    def __repr__(self) -> str:
        return f"<Feedback id={self.id} is_read={self.is_read}>"
