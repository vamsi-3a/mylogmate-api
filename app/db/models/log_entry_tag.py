"""log_entry_tags association table (many-to-many: LogEntry ↔ Tag).

Defined as a plain SQLAlchemy Table (no ORM class) since it carries no
extra columns beyond the two foreign keys.

Both FKs have ON DELETE CASCADE:
  - Deleting a LogEntry removes all its tag associations.
  - Deleting a Tag removes all its log associations.

The ix_log_entry_tags_tag_id index enables efficient reverse lookup:
"all log entries that use a given tag" — needed for recall filtering and
tag deletion flows.
"""

from sqlalchemy import Column, ForeignKey, Index, Table
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

log_entry_tags = Table(
    "log_entry_tags",
    Base.metadata,
    Column(
        "log_entry_id",
        UUID(as_uuid=True),
        ForeignKey("log_entries.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
    Column(
        "tag_id",
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
)

# Reverse lookup index: "all log entries for a given tag"
# Needed for tag-filtered recall queries and tag delete/rename flows.
Index("ix_log_entry_tags_tag_id", log_entry_tags.c.tag_id)
