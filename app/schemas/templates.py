"""Template request/response schemas.

Sample templates (is_sample=True, user_id=None) are seeded via `make seed`.
Users may create personal templates (is_sample=False).
Template content is NOT encrypted — it's structural format text.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ── Request schemas ────────────────────────────────────────────────────────


class CreateTemplateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1, max_length=5_000)


class UpdateTemplateRequest(BaseModel):
    """Partial update — only provided fields are changed."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    content: str | None = Field(default=None, min_length=1, max_length=5_000)


# ── Response schemas ───────────────────────────────────────────────────────


class TemplateResponse(BaseModel):
    id: uuid.UUID
    # None for sample templates
    user_id: uuid.UUID | None
    name: str
    content: str
    is_sample: bool
    category: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
