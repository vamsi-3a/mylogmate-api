"""Context request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ── Request schemas ────────────────────────────────────────────────────────


class CreateContextRequest(BaseModel):
    type: str = Field(
        ...,
        pattern=r"^(self|teammate|project)$",
        description="Context type: self | teammate | project",
    )
    name: str = Field(..., min_length=1, max_length=100)


class UpdateContextRequest(BaseModel):
    """Partial update — only name can be changed (type is immutable)."""

    name: str = Field(..., min_length=1, max_length=100)


# ── Response schemas ───────────────────────────────────────────────────────


class ContextResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
