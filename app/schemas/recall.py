"""AI recall / chat request/response schemas.

Chat content is always decrypted before being returned in responses —
never expose content_encrypted from chat_messages directly.

Response shapes match the frontend's ChatSession / ChatMessage / RecallQueryResponse
types — the React recall pages can consume these directly.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ── Request schemas ────────────────────────────────────────────────────────


class RecallQueryRequest(BaseModel):
    """Ask a question against a user's log history within a context."""

    # Accepts a real UUID or the magic string "self" — resolved at the route layer.
    context_id: str = Field(..., min_length=1, max_length=64)
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
    session_id: uuid.UUID
    role: str  # 'user' | 'assistant'
    # Decrypted content — NEVER the raw content_encrypted value
    content: str
    source_log_ids: list[uuid.UUID] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSessionResponse(BaseModel):
    """Chat session summary (list view — no messages)."""

    id: uuid.UUID
    user_id: uuid.UUID
    context_id: uuid.UUID
    title: str
    message_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSessionDetailResponse(BaseModel):
    """Chat session with full message history (detail view)."""

    id: uuid.UUID
    user_id: uuid.UUID
    context_id: uuid.UUID
    title: str
    message_count: int = 0
    messages: list[ChatMessageResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecallQueryResponse(BaseModel):
    """Returned after a successful AI recall query."""

    answer: str
    source_log_ids: list[uuid.UUID] = []
    latency_ms: int = 0
    chat_session_id: uuid.UUID
