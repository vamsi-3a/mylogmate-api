"""Context request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ── Request schemas ────────────────────────────────────────────────────────


class CreateContextRequest(BaseModel):
    type: str = Field(
        ...,
        pattern=r"^(self|team|project)$",
        description="Context type: self | team | project",
    )
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class UpdateContextRequest(BaseModel):
    """Partial update — only provided fields are changed."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


# ── Response schemas ───────────────────────────────────────────────────────


class ContextResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
