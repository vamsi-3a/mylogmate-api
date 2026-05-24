"""Tag request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ── Request schemas ────────────────────────────────────────────────────────


class CreateTagRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    color: str | None = Field(
        default=None,
        pattern=r"^#[0-9a-fA-F]{6}$",
        description="Hex color code, e.g. #FF5733",
    )


class UpdateTagRequest(BaseModel):
    """Partial update — only provided fields are changed."""

    name: str | None = Field(default=None, min_length=1, max_length=50)
    color: str | None = Field(
        default=None,
        pattern=r"^#[0-9a-fA-F]{6}$",
        description="Hex color code, e.g. #FF5733",
    )


# ── Response schemas ───────────────────────────────────────────────────────


class TagResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    color: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
