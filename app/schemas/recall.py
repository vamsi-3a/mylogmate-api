"""AI recall / chat request/response schemas.

Chat content is always decrypted before being returned in responses —
never expose content_encrypted from chat_messages directly.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ── Request schemas ────────────────────────────────────────────────────────


class RecallQueryRequest(BaseModel):
    """Ask a question against a user's log history within a context."""

    context_id: uuid.UUID
    query: str = Field(
        ...,
        min_length=1,
        max_length=1_000,
        description="Natural-language question about the user's work logs",
    )
    # Optionally continue an existing session; creates a new one if omitted
    chat_session_id: uuid.UUID | None = None


# ── Response schemas ───────────────────────────────────────────────────────


class ChatMessageResponse(BaseModel):
    """Single chat turn — content is always decrypted."""

    id: uuid.UUID
    role: str  # 'user' | 'assistant'
    # Decrypted content — NEVER the raw content_encrypted value
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSessionResponse(BaseModel):
    """Chat session summary (list view — no messages)."""

    id: uuid.UUID
    context_id: uuid.UUID | None
    title: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSessionDetailResponse(BaseModel):
    """Chat session with full message history (detail view)."""

    id: uuid.UUID
    context_id: uuid.UUID | None
    title: str | None
    messages: list[ChatMessageResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecallQueryResponse(BaseModel):
    """Returned after a successful AI recall query."""

    answer: str
    chat_session_id: uuid.UUID
    # The assistant's new message — client can append it locally
    message: ChatMessageResponse
    # How many daily AI queries the user has used vs. their limit
    queries_used_today: int
    daily_limit: int
