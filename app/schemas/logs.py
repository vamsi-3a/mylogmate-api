"""Log entry request/response schemas.

Rules:
- content is always decrypted before being placed in a response — never
  return content_encrypted from the DB directly.
- tag_ids in requests are UUIDs; the service resolves them to Tag objects.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.tags import TagResponse

# ── Request schemas ────────────────────────────────────────────────────────


class CreateLogRequest(BaseModel):
    # Accepts a real UUID or the magic string "self" — resolved at the route layer.
    context_id: str = Field(..., min_length=1, max_length=64)
    content: str = Field(..., min_length=1, max_length=10_000)
    date_type: str = Field(
        ...,
        pattern=r"^(daily|weekly|custom)$",
        description="daily | weekly | custom",
    )
    date_start: date
    date_end: date
    tag_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)

    @field_validator("date_end")
    @classmethod
    def end_after_start(cls, v: date, info: object) -> date:
        start = getattr(info, "data", {}).get("date_start")
        if start and v < start:
            raise ValueError("date_end must be >= date_start")
        return v


class UpdateLogRequest(BaseModel):
    """Partial update — only provided fields are changed."""

    content: str | None = Field(default=None, min_length=1, max_length=10_000)
    date_type: str | None = Field(
        default=None,
        pattern=r"^(daily|weekly|custom)$",
    )
    date_start: date | None = None
    date_end: date | None = None
    tag_ids: list[uuid.UUID] | None = Field(default=None, max_length=20)

    @field_validator("date_end")
    @classmethod
    def end_after_start(cls, v: date | None, info: object) -> date | None:
        if v is None:
            return v
        start = getattr(info, "data", {}).get("date_start")
        if start and v < start:
            raise ValueError("date_end must be >= date_start")
        return v


class AssignTagsRequest(BaseModel):
    """Replace the full set of tags on a log entry."""

    tag_ids: list[uuid.UUID] = Field(..., max_length=20)


# ── Response schemas ───────────────────────────────────────────────────────


class LogResponse(BaseModel):
    id: uuid.UUID
    context_id: uuid.UUID
    # Decrypted content — NEVER the raw content_encrypted value
    content: str
    date_type: str
    date_start: date
    date_end: date
    embedding_status: str
    tags: list[TagResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Calendar response schemas ──────────────────────────────────────────────


class CalendarDayResponse(BaseModel):
    """Summary for a single calendar day."""

    date: date
    log_count: int
    has_entries: bool


class CalendarMonthResponse(BaseModel):
    """Full month view — one CalendarDayResponse per day."""

    year: int
    month: int
    days: list[CalendarDayResponse]
