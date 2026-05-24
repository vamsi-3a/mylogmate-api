"""Feedback request/response schemas.

Feedback is voluntarily submitted plain text — no encryption required.
is_read is toggled by admins only.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ── Request schemas ────────────────────────────────────────────────────────


class CreateFeedbackRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2_000)


# ── Response schemas ───────────────────────────────────────────────────────


class FeedbackResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    content: str
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
