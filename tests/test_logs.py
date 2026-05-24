"""Log entry endpoint tests.

All DB calls and encryption are mocked — no real PostgreSQL or Fernet required.

Coverage:
- GET  /api/v1/logs                 — list paginated, with filters, unauthenticated,
                                      context not found
- POST /api/v1/logs                 — create, invalid context, invalid tags, validation
- GET  /api/v1/logs/{id}            — found, not found, unauthenticated
- PATCH /api/v1/logs/{id}           — partial update, date validation, not found
- DELETE /api/v1/logs/{id}          — soft delete, not found, unauthenticated
- PUT  /api/v1/logs/{id}/tags       — assign tags, invalid tags
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import override_current_user

# ── Helpers ───────────────────────────────────────────────────────────────


def _make_user(**kwargs: Any) -> Any:
    from unittest.mock import MagicMock

    user = MagicMock()
    user.id = kwargs.get("id", uuid.uuid4())
    user.is_active = True
    return user


def _make_log_response(
    content: str = "Finished the auth module",
    context_id: uuid.UUID | None = None,
) -> Any:
    from app.schemas.logs import LogResponse

    return LogResponse(
        id=uuid.uuid4(),
        context_id=context_id or uuid.uuid4(),
        content=content,
        date_type="daily",
        date_start=date(2026, 5, 20),
        date_end=date(2026, 5, 20),
        embedding_status="pending",
        tags=[],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _log_payload(**kwargs: Any) -> dict[str, Any]:
    """Build a valid CreateLogRequest payload."""
    return {
        "context_id": str(kwargs.get("context_id", uuid.uuid4())),
        "content": kwargs.get("content", "Did some work today"),
        "date_type": kwargs.get("date_type", "daily"),
        "date_start": str(kwargs.get("date_start", "2026-05-20")),
        "date_end": str(kwargs.get("date_end", "2026-05-20")),
        "tag_ids": kwargs.get("tag_ids", []),
    }


# ── GET /logs ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_logs_success(client: AsyncClient) -> None:
    """Returns paginated list of log entries."""
    user = _make_user()
    context_id = uuid.uuid4()
    logs = [_make_log_response(context_id=context_id)]

    with (
        override_current_user(user),
        patch("app.services.logs.list_logs", new_callable=AsyncMock) as mock_list,
    ):
        mock_list.return_value = (logs, 1)
        resp = await client.get(
            "/api/v1/logs",
            params={"context_id": str(context_id)},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["total"] == 1
    assert len(body["data"]) == 1
    assert body["data"][0]["content"] == "Finished the auth module"


@pytest.mark.asyncio
async def test_list_logs_with_pagination(client: AsyncClient) -> None:
    """Passes page and page_size to the service."""
    user = _make_user()
    context_id = uuid.uuid4()

    with (
        override_current_user(user),
        patch("app.services.logs.list_logs", new_callable=AsyncMock) as mock_list,
    ):
        mock_list.return_value = ([], 0)
        resp = await client.get(
            "/api/v1/logs",
            params={"context_id": str(context_id), "page": 2, "page_size": 10},
        )

    assert resp.status_code == 200
    assert resp.json()["page"] == 2
    assert resp.json()["page_size"] == 10
    # page and page_size are passed as keyword arguments to the service
    assert mock_list.call_args.kwargs["page"] == 2
    assert mock_list.call_args.kwargs["page_size"] == 10


@pytest.mark.asyncio
async def test_list_logs_context_not_found(client: AsyncClient) -> None:
    """Returns 404 when context doesn't belong to user."""
    from app.core.exceptions import NotFoundError

    user = _make_user()

    with (
        override_current_user(user),
        patch("app.services.logs.list_logs", new_callable=AsyncMock) as mock_list,
    ):
        mock_list.side_effect = NotFoundError("Context")
        resp = await client.get(
            "/api/v1/logs",
            params={"context_id": str(uuid.uuid4())},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_logs_unauthenticated(client: AsyncClient) -> None:
    """Returns 401 without token."""
    resp = await client.get(
        "/api/v1/logs",
        params={"context_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_logs_missing_context_id(client: AsyncClient) -> None:
    """Returns 422 when context_id query param is missing."""
    user = _make_user()

    with override_current_user(user):
        resp = await client.get("/api/v1/logs")

    assert resp.status_code == 422


# ── POST /logs ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_log_success(client: AsyncClient) -> None:
    """Creates a log entry and returns 201 with decrypted content."""
    user = _make_user()
    log_resp = _make_log_response("Did some work today")

    with (
        override_current_user(user),
        patch("app.services.logs.create_log", new_callable=AsyncMock) as mock_create,
    ):
        mock_create.return_value = log_resp
        resp = await client.post("/api/v1/logs", json=_log_payload())

    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["content"] == "Did some work today"
    assert body["data"]["embedding_status"] == "pending"


@pytest.mark.asyncio
async def test_create_log_invalid_context(client: AsyncClient) -> None:
    """Returns 404 when context doesn't belong to the user."""
    from app.core.exceptions import NotFoundError

    user = _make_user()

    with (
        override_current_user(user),
        patch("app.services.logs.create_log", new_callable=AsyncMock) as mock_create,
    ):
        mock_create.side_effect = NotFoundError("Context")
        resp = await client.post("/api/v1/logs", json=_log_payload())

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_log_invalid_tags(client: AsyncClient) -> None:
    """Returns 422 when any tag_id doesn't belong to the user."""
    from app.core.exceptions import ValidationError

    user = _make_user()

    with (
        override_current_user(user),
        patch("app.services.logs.create_log", new_callable=AsyncMock) as mock_create,
    ):
        mock_create.side_effect = ValidationError(
            "One or more tag IDs are invalid or don't belong to you"
        )
        resp = await client.post(
            "/api/v1/logs",
            json=_log_payload(tag_ids=[str(uuid.uuid4())]),
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_log_validation_error_date_range(client: AsyncClient) -> None:
    """Returns 422 when date_end < date_start (Pydantic cross-field validator)."""
    user = _make_user()

    with override_current_user(user):
        resp = await client.post(
            "/api/v1/logs",
            json=_log_payload(date_start="2026-05-20", date_end="2026-05-19"),
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_log_content_too_long(client: AsyncClient) -> None:
    """Returns 422 when content exceeds 10,000 chars."""
    user = _make_user()

    with override_current_user(user):
        resp = await client.post(
            "/api/v1/logs",
            json=_log_payload(content="x" * 10_001),
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_log_invalid_date_type(client: AsyncClient) -> None:
    """Returns 422 for an unknown date_type."""
    user = _make_user()

    with override_current_user(user):
        resp = await client.post(
            "/api/v1/logs",
            json=_log_payload(date_type="monthly"),
        )

    assert resp.status_code == 422


# ── GET /logs/{log_id} ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_log_success(client: AsyncClient) -> None:
    """Returns a single log entry with decrypted content."""
    user = _make_user()
    log_resp = _make_log_response("Reviewed PRs today")
    log_id = log_resp.id

    with (
        override_current_user(user),
        patch("app.services.logs.get_log", new_callable=AsyncMock) as mock_get,
    ):
        mock_get.return_value = log_resp
        resp = await client.get(f"/api/v1/logs/{log_id}")

    assert resp.status_code == 200
    assert resp.json()["data"]["content"] == "Reviewed PRs today"


@pytest.mark.asyncio
async def test_get_log_not_found(client: AsyncClient) -> None:
    """Returns 404 for a missing or deleted entry."""
    from app.core.exceptions import NotFoundError

    user = _make_user()

    with (
        override_current_user(user),
        patch("app.services.logs.get_log", new_callable=AsyncMock) as mock_get,
    ):
        mock_get.side_effect = NotFoundError("Log entry")
        resp = await client.get(f"/api/v1/logs/{uuid.uuid4()}")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_log_unauthenticated(client: AsyncClient) -> None:
    """Returns 401 without token."""
    resp = await client.get(f"/api/v1/logs/{uuid.uuid4()}")
    assert resp.status_code == 401


# ── PATCH /logs/{log_id} ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_log_success(client: AsyncClient) -> None:
    """Partially updates content and returns updated entry."""
    user = _make_user()
    updated_log = _make_log_response("Updated content")
    log_id = updated_log.id

    with (
        override_current_user(user),
        patch("app.services.logs.update_log", new_callable=AsyncMock) as mock_update,
    ):
        mock_update.return_value = updated_log
        resp = await client.patch(
            f"/api/v1/logs/{log_id}",
            json={"content": "Updated content"},
        )

    assert resp.status_code == 200
    assert resp.json()["data"]["content"] == "Updated content"


@pytest.mark.asyncio
async def test_update_log_not_found(client: AsyncClient) -> None:
    """Returns 404 for a missing or already-deleted entry."""
    from app.core.exceptions import NotFoundError

    user = _make_user()

    with (
        override_current_user(user),
        patch("app.services.logs.update_log", new_callable=AsyncMock) as mock_update,
    ):
        mock_update.side_effect = NotFoundError("Log entry")
        resp = await client.patch(
            f"/api/v1/logs/{uuid.uuid4()}",
            json={"content": "New content"},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_log_invalid_date_range(client: AsyncClient) -> None:
    """Returns 422 when service raises ValidationError for bad date range."""
    from app.core.exceptions import ValidationError

    user = _make_user()

    with (
        override_current_user(user),
        patch("app.services.logs.update_log", new_callable=AsyncMock) as mock_update,
    ):
        mock_update.side_effect = ValidationError("date_end must be >= date_start")
        resp = await client.patch(
            f"/api/v1/logs/{uuid.uuid4()}",
            json={"date_start": "2026-05-20", "date_end": "2026-05-19"},
        )

    assert resp.status_code == 422


# ── DELETE /logs/{log_id} ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_log_success(client: AsyncClient) -> None:
    """Soft-deletes a log entry and returns 200."""
    user = _make_user()

    with (
        override_current_user(user),
        patch("app.services.logs.delete_log", new_callable=AsyncMock) as mock_delete,
    ):
        mock_delete.return_value = None
        resp = await client.delete(f"/api/v1/logs/{uuid.uuid4()}")

    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_delete_log_not_found(client: AsyncClient) -> None:
    """Returns 404 when entry doesn't exist or already deleted."""
    from app.core.exceptions import NotFoundError

    user = _make_user()

    with (
        override_current_user(user),
        patch("app.services.logs.delete_log", new_callable=AsyncMock) as mock_delete,
    ):
        mock_delete.side_effect = NotFoundError("Log entry")
        resp = await client.delete(f"/api/v1/logs/{uuid.uuid4()}")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_log_unauthenticated(client: AsyncClient) -> None:
    """Returns 401 without token."""
    resp = await client.delete(f"/api/v1/logs/{uuid.uuid4()}")
    assert resp.status_code == 401


# ── PUT /logs/{log_id}/tags ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_assign_tags_success(client: AsyncClient) -> None:
    """Replaces tags on a log entry and returns updated entry."""
    user = _make_user()
    tag_id = uuid.uuid4()
    log_resp = _make_log_response()
    log_id = log_resp.id

    with (
        override_current_user(user),
        patch("app.services.logs.assign_tags", new_callable=AsyncMock) as mock_assign,
    ):
        mock_assign.return_value = log_resp
        resp = await client.put(
            f"/api/v1/logs/{log_id}/tags",
            json={"tag_ids": [str(tag_id)]},
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_assign_tags_invalid(client: AsyncClient) -> None:
    """Returns 422 when any tag doesn't belong to the user."""
    from app.core.exceptions import ValidationError

    user = _make_user()

    with (
        override_current_user(user),
        patch("app.services.logs.assign_tags", new_callable=AsyncMock) as mock_assign,
    ):
        mock_assign.side_effect = ValidationError(
            "One or more tag IDs are invalid or don't belong to you"
        )
        resp = await client.put(
            f"/api/v1/logs/{uuid.uuid4()}/tags",
            json={"tag_ids": [str(uuid.uuid4())]},
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_assign_tags_log_not_found(client: AsyncClient) -> None:
    """Returns 404 when log entry doesn't exist."""
    from app.core.exceptions import NotFoundError

    user = _make_user()

    with (
        override_current_user(user),
        patch("app.services.logs.assign_tags", new_callable=AsyncMock) as mock_assign,
    ):
        mock_assign.side_effect = NotFoundError("Log entry")
        resp = await client.put(
            f"/api/v1/logs/{uuid.uuid4()}/tags",
            json={"tag_ids": []},
        )

    assert resp.status_code == 404
