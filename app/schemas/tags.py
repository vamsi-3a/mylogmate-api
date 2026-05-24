"""Tag request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ── Request schemas ────────────────────────────────────────────────────────


class CreateTagRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)


class UpdateTagRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)


# ── Response schemas ───────────────────────────────────────────────────────


class TagResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
