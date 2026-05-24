"""Unit tests for the recall API and service.

All external calls (RAG pipeline, Qdrant, LLM, DB) are mocked.

Coverage:
- POST /recall
  — happy path: returns AI answer + chat session metadata
  — context not found: 404
  — rate limit exceeded: 422
  — unauthenticated: 401
- GET /recall/sessions
  — happy path: paginated list
  — unauthenticated: 401
- GET /recall/sessions/{id}
  — happy path: session with messages
  — not found: 404
  — unauthenticated: 401
- DELETE /recall/sessions/{id}
  — happy path: session deleted
  — not found: 404
  — unauthenticated: 401
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import override_current_user

# ── Helpers ───────────────────────────────────────────────────────────────


def _make_user(user_id: uuid.UUID | None = None) -> MagicMock:
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.username = "testuser"
    user.is_admin = False
    return user


def _make_recall_response(session_id: uuid.UUID | None = None) -> MagicMock:
    from app.schemas.recall import ChatMessageResponse, RecallQueryResponse

    msg_id = uuid.uuid4()
    from datetime import UTC, datetime

    msg = ChatMessageResponse(
        id=msg_id,
        role="assistant",
        content="Here is a summary of your work.",
        created_at=datetime.now(UTC),
    )
    sid = session_id or uuid.uuid4()
    return RecallQueryResponse(
        answer="Here is a summary of your work.",
        chat_session_id=sid,
        message=msg,
        queries_used_today=1,
        daily_limit=50,
    )


def _make_session_response(session_id: uuid.UUID | None = None) -> MagicMock:
    from datetime import UTC, datetime

    from app.schemas.recall import ChatSessionResponse

    return ChatSessionResponse(
        id=session_id or uuid.uuid4(),
        context_id=uuid.uuid4(),
        title="My first recall",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _make_session_detail(session_id: uuid.UUID | None = None) -> MagicMock:
    from datetime import UTC, datetime

    from app.schemas.recall import ChatMessageResponse, ChatSessionDetailResponse

    sid = session_id or uuid.uuid4()
    msg = ChatMessageResponse(
        id=uuid.uuid4(),
        role="user",
        content="What did I work on last week?",
        created_at=datetime.now(UTC),
    )
    return ChatSessionDetailResponse(
        id=sid,
        context_id=uuid.uuid4(),
        title="Last week's work",
        messages=[msg],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


# ── POST /recall ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_recall_query_success(client: AsyncClient) -> None:
    """Happy path: returns AI answer with session and message metadata."""
    user = _make_user()
    context_id = uuid.uuid4()
    recall_resp = _make_recall_response()

    with (
        override_current_user(user),
        patch(
            "app.api.v1.recall.recall_service.recall_query",
            new=AsyncMock(return_value=recall_resp),
        ),
    ):
        resp = await client.post(
            "/api/v1/recall",
            json={"context_id": str(context_id), "query": "What did I work on last week?"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "answer" in data["data"]
    assert data["data"]["queries_used_today"] == 1


@pytest.mark.asyncio
async def test_recall_query_context_not_found(client: AsyncClient) -> None:
    """Returns 404 when context doesn't belong to the user."""
    from app.core.exceptions import NotFoundError

    user = _make_user()

    with (
        override_current_user(user),
        patch(
            "app.api.v1.recall.recall_service.recall_query",
            new=AsyncMock(side_effect=NotFoundError("Context")),
        ),
    ):
        resp = await client.post(
            "/api/v1/recall",
            json={"context_id": str(uuid.uuid4()), "query": "any question"},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_recall_query_rate_limit_exceeded(client: AsyncClient) -> None:
    """Returns 422 when daily AI query limit is reached."""
    from app.core.exceptions import ValidationError

    user = _make_user()

    with (
        override_current_user(user),
        patch(
            "app.api.v1.recall.recall_service.recall_query",
            new=AsyncMock(side_effect=ValidationError("Daily AI query limit of 50 reached")),
        ),
    ):
        resp = await client.post(
            "/api/v1/recall",
            json={"context_id": str(uuid.uuid4()), "query": "any question"},
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_recall_query_unauthenticated(client: AsyncClient) -> None:
    """Returns 401 when the request has no auth credentials."""
    resp = await client.post(
        "/api/v1/recall",
        json={"context_id": str(uuid.uuid4()), "query": "any question"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_recall_query_missing_query_field(client: AsyncClient) -> None:
    """Returns 422 when required query field is missing."""
    user = _make_user()
    with override_current_user(user):
        resp = await client.post(
            "/api/v1/recall",
            json={"context_id": str(uuid.uuid4())},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_recall_query_empty_query(client: AsyncClient) -> None:
    """Returns 422 when query is empty string (min_length=1)."""
    user = _make_user()
    with override_current_user(user):
        resp = await client.post(
            "/api/v1/recall",
            json={"context_id": str(uuid.uuid4()), "query": ""},
        )
    assert resp.status_code == 422


# ── GET /recall/sessions ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_sessions_success(client: AsyncClient) -> None:
    """Happy path: returns paginated chat session list."""
    user = _make_user()
    sessions = [_make_session_response() for _ in range(3)]

    with (
        override_current_user(user),
        patch(
            "app.api.v1.recall.recall_service.list_chat_sessions",
            new=AsyncMock(return_value=(sessions, 3)),
        ),
    ):
        resp = await client.get("/api/v1/recall/sessions")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["data"]) == 3


@pytest.mark.asyncio
async def test_list_sessions_unauthenticated(client: AsyncClient) -> None:
    """Returns 401 when unauthenticated."""
    resp = await client.get("/api/v1/recall/sessions")
    assert resp.status_code == 401


# ── GET /recall/sessions/{id} ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_session_success(client: AsyncClient) -> None:
    """Happy path: returns session with full message history."""
    user = _make_user()
    session_id = uuid.uuid4()
    detail = _make_session_detail(session_id)

    with (
        override_current_user(user),
        patch(
            "app.api.v1.recall.recall_service.get_chat_session",
            new=AsyncMock(return_value=detail),
        ),
    ):
        resp = await client.get(f"/api/v1/recall/sessions/{session_id}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert len(data["data"]["messages"]) == 1


@pytest.mark.asyncio
async def test_get_session_not_found(client: AsyncClient) -> None:
    """Returns 404 when session doesn't exist."""
    from app.core.exceptions import NotFoundError

    user = _make_user()

    with (
        override_current_user(user),
        patch(
            "app.api.v1.recall.recall_service.get_chat_session",
            new=AsyncMock(side_effect=NotFoundError("Chat session")),
        ),
    ):
        resp = await client.get(f"/api/v1/recall/sessions/{uuid.uuid4()}")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_session_unauthenticated(client: AsyncClient) -> None:
    """Returns 401 when unauthenticated."""
    resp = await client.get(f"/api/v1/recall/sessions/{uuid.uuid4()}")
    assert resp.status_code == 401


# ── DELETE /recall/sessions/{id} ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_session_success(client: AsyncClient) -> None:
    """Happy path: deletes a chat session."""
    user = _make_user()

    with (
        override_current_user(user),
        patch(
            "app.api.v1.recall.recall_service.delete_chat_session",
            new=AsyncMock(return_value=None),
        ),
    ):
        resp = await client.delete(f"/api/v1/recall/sessions/{uuid.uuid4()}")

    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_delete_session_not_found(client: AsyncClient) -> None:
    """Returns 404 when session doesn't exist."""
    from app.core.exceptions import NotFoundError

    user = _make_user()

    with (
        override_current_user(user),
        patch(
            "app.api.v1.recall.recall_service.delete_chat_session",
            new=AsyncMock(side_effect=NotFoundError("Chat session")),
        ),
    ):
        resp = await client.delete(f"/api/v1/recall/sessions/{uuid.uuid4()}")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_session_unauthenticated(client: AsyncClient) -> None:
    """Returns 401 when unauthenticated."""
    resp = await client.delete(f"/api/v1/recall/sessions/{uuid.uuid4()}")
    assert resp.status_code == 401
