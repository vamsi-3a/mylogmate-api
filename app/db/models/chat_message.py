"""ChatMessage ORM model — append-only message log per chat session.

SECURITY: content_encrypted must NEVER be plain text.
Chat messages contain the user's exact questions and AI summaries of their
work logs — sensitive personal data under the same privacy guarantee as
log entries. Encrypt/decrypt via app.core.security.

role values: 'user' (human) | 'assistant' (AI)
Messages are append-only — no updates, no soft delete.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.chat_session import ChatSession


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_chat_messages_role",
        ),
        # Fetch all messages in a session in chronological order
        Index("ix_chat_messages_session_created", "chat_session_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chat_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 'user' | 'assistant'
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    # AES-256 (Fernet) encrypted — NEVER plain text
    content_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    # Append-only — no updated_at
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    # ── Relationships ─────────────────────────────────────────────────────
    chat_session: Mapped[ChatSession] = relationship(
        "ChatSession", back_populates="messages"
    )

    def __repr__(self) -> str:
        return f"<ChatMessage id={self.id} role={self.role!r}>"
