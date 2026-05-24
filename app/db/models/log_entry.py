"""LogEntry ORM model — the atomic unit of MyLogMate.

SECURITY: content_encrypted must NEVER be plain text.
Always encrypt via app.core.security.encrypt_content() before write.
Always decrypt via app.core.security.decrypt_content() after read.

embedding_status lifecycle:
  pending  → row created or edited (Celery task dispatched)
  embedded → Celery task successfully upserted vector in Qdrant
  failed   → Celery task exhausted all retries

On soft delete (is_deleted=True): Celery delete_embedding task removes
the Qdrant vector. The row is kept for data-recovery purposes.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.log_entry_tag import log_entry_tags

if TYPE_CHECKING:
    from app.db.models.context import Context
    from app.db.models.tag import Tag
    from app.db.models.user import User


class LogEntry(Base):
    __tablename__ = "log_entries"
    __table_args__ = (
        # ── Check constraints ─────────────────────────────────────────
        CheckConstraint(
            "date_type IN ('daily', 'weekly', 'custom')",
            name="ck_log_entries_date_type",
        ),
        CheckConstraint(
            "embedding_status IN ('pending', 'embedded', 'failed')",
            name="ck_log_entries_embedding_status",
        ),
        CheckConstraint(
            "date_end >= date_start",
            name="ck_log_entries_date_range",
        ),
        # ── Composite indexes ─────────────────────────────────────────
        # Primary browsing: user's logs in a context within a date range
        Index(
            "ix_log_entries_user_context_dates",
            "user_id", "context_id", "date_start", "date_end",
            postgresql_where="is_deleted = false",
        ),
        # Soft-delete filter
        Index("ix_log_entries_user_deleted", "user_id", "is_deleted"),
        # Calendar view: fill dots on a given month
        Index(
            "ix_log_entries_user_date_start",
            "user_id", "date_start",
            postgresql_where="is_deleted = false",
        ),
        # Celery retry job: find pending/failed entries
        Index(
            "ix_log_entries_embedding_status",
            "embedding_status",
            postgresql_where="is_deleted = false",
        ),
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
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contexts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # AES-256 (Fernet) encrypted — NEVER plain text
    content_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    # 'pending' | 'embedded' | 'failed'
    embedding_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    # 'daily' | 'weekly' | 'custom'
    date_type: Mapped[str] = mapped_column(String(10), nullable=False)
    date_start: Mapped[date] = mapped_column(Date, nullable=False)
    # Same as date_start for daily entries
    date_end: Mapped[date] = mapped_column(Date, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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
    user: Mapped[User] = relationship("User", back_populates="log_entries")
    context: Mapped[Context] = relationship("Context", back_populates="log_entries")
    # selectin: fetch tags in one extra SELECT (avoids N+1 when listing entries)
    tags: Mapped[list[Tag]] = relationship(
        "Tag",
        secondary=log_entry_tags,
        back_populates="log_entries",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<LogEntry id={self.id} date_start={self.date_start} "
            f"status={self.embedding_status!r}>"
        )
