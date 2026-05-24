---
name: sqlalchemy-models
description: Use when creating/modifying SQLAlchemy ORM models in app/db/models/. Covers model structure, column types, relationships, indexes, constraints, UUID PKs, timestamps. Trigger on any file in app/db/models/.
---

# SQLAlchemy Model Patterns

## Model Template
```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Date, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base

class LogEntry(Base):
    __tablename__ = "log_entries"
    __table_args__ = (
        Index("ix_log_entries_user_context_date", "user_id", "context_id", "date_start", "date_end"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    context_id = Column(UUID(as_uuid=True), ForeignKey("contexts.id", ondelete="CASCADE"), nullable=False, index=True)
    content_encrypted = Column(Text, nullable=False)
    date_type = Column(String(10), nullable=False)
    date_start = Column(Date, nullable=False)
    date_end = Column(Date, nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    context = relationship("Context", back_populates="log_entries")
    tags = relationship("Tag", secondary="log_entry_tags", back_populates="log_entries", lazy="selectin")
```

## Rules
- UUID PK: `Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)`
- Timestamps: `DateTime(timezone=True)` with UTC defaults
- Add `index=True` on all FK columns
- Use `ondelete="CASCADE"` on FKs where parent deletion should cascade
- Composite indexes for multi-column query patterns
- One model per file in app/db/models/
- Import all models in app/db/models/__init__.py for Alembic detection
- Soft delete: only on log_entries (is_deleted). Everything else: hard delete (v1 has no delete for teammates/projects/tags)
- Unique constraints where needed: (user_id, type, name) on contexts, (user_id, name) on tags
