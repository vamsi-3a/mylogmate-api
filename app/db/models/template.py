"""Template ORM model.

Two kinds of templates coexist in the same table:
  - Sample templates: user_id=NULL, is_sample=True (seeded via `make seed`)
  - User templates:   user_id=<uuid>, is_sample=False (user-created)

Template content is NOT encrypted — it's structural format text, not
sensitive user data. Users create templates to speed up log entry creation.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User


class Template(Base):
    __tablename__ = "templates"
    __table_args__ = (
        Index("ix_templates_user_id", "user_id"),
        Index("ix_templates_is_sample", "is_sample"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # NULL for sample templates (system-provided)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Plain text — not encrypted (structural format, not sensitive content)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_sample: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # For sample templates: 'software_engineer', 'engineering_manager', etc.
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
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
    user: Mapped[User | None] = relationship("User", back_populates="templates")

    def __repr__(self) -> str:
        kind = "sample" if self.is_sample else "user"
        return f"<Template id={self.id} name={self.name!r} kind={kind}>"
