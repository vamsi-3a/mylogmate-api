"""Unit tests for the feedback API.

Coverage:
- POST /feedback
  — happy path: creates feedback and returns it
  — content too long (> 2000 chars): 422
  — empty content: 422
  — unauthenticated: 401
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import override_current_user


def _make_user() -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.username = "testuser"
    user.is_admin = False
    return user


def _make_feedback_response() -> MagicMock:
    from app.schemas.feedback import FeedbackResponse

    return FeedbackResponse(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        content="This app is great!",
        is_read=False,
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_submit_feedback_success(client: AsyncClient) -> None:
    """Happy path: feedback is created and returned."""
    user = _make_user()
    fb = _make_feedback_response()

    with (
        override_current_user(user),
        patch(
            "app.api.v1.feedback.feedback_service.submit_feedback",
            new=AsyncMock(return_value=fb),
        ),
    ):
        resp = await client.post(
            "/api/v1/feedback",
            json={"content": "This app is great!"},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["content"] == "This app is great!"
    assert data["data"]["is_read"] is False


@pytest.mark.asyncio
async def test_submit_feedback_content_too_long(client: AsyncClient) -> None:
    """Returns 422 when content exceeds 2000 characters."""
    user = _make_user()
    with override_current_user(user):
        resp = await client.post(
            "/api/v1/feedback",
            json={"content": "x" * 2001},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_submit_feedback_empty_content(client: AsyncClient) -> None:
    """Returns 422 when content is empty."""
    user = _make_user()
    with override_current_user(user):
        resp = await client.post(
            "/api/v1/feedback",
            json={"content": ""},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_submit_feedback_missing_content(client: AsyncClient) -> None:
    """Returns 422 when content field is missing."""
    user = _make_user()
    with override_current_user(user):
        resp = await client.post("/api/v1/feedback", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_submit_feedback_unauthenticated(client: AsyncClient) -> None:
    """Returns 401 when unauthenticated."""
    resp = await client.post(
        "/api/v1/feedback",
        json={"content": "This app is great!"},
    )
    assert resp.status_code == 401
