"""Unit tests for the admin API.

All DB calls are mocked through service layer patches.

Coverage:
- GET /admin/stats
  — happy path (admin): returns stats
  — forbidden (non-admin): 403
  — unauthenticated: 401
- GET /admin/users
  — happy path: paginated user list
  — with search: forwarded to service
  — forbidden: 403
- POST /admin/users/{id}/toggle-active
  — happy path: toggles user active status
  — self-toggle: 400
  — user not found: 404
  — forbidden: 403
- GET /admin/feedback
  — happy path: paginated feedback list
  — unread_only filter: forwarded to service
  — forbidden: 403
- POST /admin/feedback/{id}/mark-read
  — happy path: marks feedback read
  — feedback not found: 404
  — forbidden: 403
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import override_current_user

# ── Helpers ───────────────────────────────────────────────────────────────


def _make_user(is_admin: bool = False, user_id: uuid.UUID | None = None) -> MagicMock:
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.username = "admin" if is_admin else "regularuser"
    user.is_admin = is_admin
    return user


def _make_stats() -> MagicMock:
    from app.schemas.admin import AdminStatsResponse, DailyCount

    return AdminStatsResponse(
        total_users=100,
        active_users_last_30d=50,
        total_log_entries=500,
        total_ai_queries=200,
        ai_queries_today=10,
        unread_feedback_count=3,
        signups_last_30d=[DailyCount(date=datetime.now(UTC).date(), count=5)],
        ai_queries_last_30d=[DailyCount(date=datetime.now(UTC).date(), count=10)],
    )


def _make_user_admin_resp(
    user_id: uuid.UUID | None = None, is_active: bool = True
) -> MagicMock:
    from app.schemas.admin import UserAdminResponse

    uid = user_id or uuid.uuid4()
    return UserAdminResponse(
        id=uid,
        username="someuser",
        email="someuser@example.com",
        auth_provider="local",
        is_admin=False,
        is_active=is_active,
        last_login_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )


def _make_feedback_resp(feedback_id: uuid.UUID | None = None) -> MagicMock:
    from app.schemas.admin import FeedbackAdminResponse

    return FeedbackAdminResponse(
        id=feedback_id or uuid.uuid4(),
        user_id=uuid.uuid4(),
        username="someuser",
        content="Great app!",
        is_read=True,
        created_at=datetime.now(UTC),
    )


# ── GET /admin/stats ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_stats_success(client: AsyncClient) -> None:
    """Admin user receives platform stats."""
    admin = _make_user(is_admin=True)
    stats = _make_stats()

    with (
        override_current_user(admin),
        patch(
            "app.api.v1.admin.admin_service.get_stats",
            new=AsyncMock(return_value=stats),
        ),
    ):
        resp = await client.get("/api/v1/admin/stats")

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["total_users"] == 100
    assert data["data"]["ai_queries_today"] == 10


@pytest.mark.asyncio
async def test_get_stats_forbidden_non_admin(client: AsyncClient) -> None:
    """Non-admin user receives 403."""
    user = _make_user(is_admin=False)
    with override_current_user(user):
        resp = await client.get("/api/v1/admin/stats")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_stats_unauthenticated(client: AsyncClient) -> None:
    """Unauthenticated request receives 401."""
    resp = await client.get("/api/v1/admin/stats")
    assert resp.status_code == 401


# ── GET /admin/users ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_users_success(client: AsyncClient) -> None:
    """Admin receives paginated user list."""
    admin = _make_user(is_admin=True)
    users = [_make_user_admin_resp() for _ in range(5)]

    with (
        override_current_user(admin),
        patch(
            "app.api.v1.admin.admin_service.list_users",
            new=AsyncMock(return_value=(users, 5)),
        ),
    ):
        resp = await client.get("/api/v1/admin/users")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["data"]) == 5


@pytest.mark.asyncio
async def test_list_users_with_search(client: AsyncClient) -> None:
    """Search parameter is forwarded to the service."""
    admin = _make_user(is_admin=True)

    with (
        override_current_user(admin),
        patch(
            "app.api.v1.admin.admin_service.list_users",
            new=AsyncMock(return_value=([], 0)),
        ) as mock_list,
    ):
        resp = await client.get("/api/v1/admin/users?search=alice")

    assert resp.status_code == 200
    _, kwargs = mock_list.call_args
    assert kwargs["search"] == "alice"


@pytest.mark.asyncio
async def test_list_users_forbidden(client: AsyncClient) -> None:
    """Non-admin receives 403."""
    user = _make_user(is_admin=False)
    with override_current_user(user):
        resp = await client.get("/api/v1/admin/users")
    assert resp.status_code == 403


# ── POST /admin/users/{id}/toggle-active ─────────────────────────────────


@pytest.mark.asyncio
async def test_toggle_user_active_success(client: AsyncClient) -> None:
    """Admin toggles a different user's active status."""
    admin = _make_user(is_admin=True)
    target_id = uuid.uuid4()
    updated = _make_user_admin_resp(user_id=target_id, is_active=False)

    with (
        override_current_user(admin),
        patch(
            "app.api.v1.admin.admin_service.toggle_user_active",
            new=AsyncMock(return_value=updated),
        ),
    ):
        resp = await client.post(f"/api/v1/admin/users/{target_id}/toggle-active")

    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is False


@pytest.mark.asyncio
async def test_toggle_user_active_self_toggle(client: AsyncClient) -> None:
    """Admin receives 400 when trying to deactivate themselves."""
    admin_id = uuid.uuid4()
    admin = _make_user(is_admin=True, user_id=admin_id)

    with override_current_user(admin):
        resp = await client.post(f"/api/v1/admin/users/{admin_id}/toggle-active")

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_toggle_user_active_not_found(client: AsyncClient) -> None:
    """Returns 404 when target user doesn't exist."""
    from app.core.exceptions import NotFoundError

    admin = _make_user(is_admin=True)

    with (
        override_current_user(admin),
        patch(
            "app.api.v1.admin.admin_service.toggle_user_active",
            new=AsyncMock(side_effect=NotFoundError("User")),
        ),
    ):
        resp = await client.post(f"/api/v1/admin/users/{uuid.uuid4()}/toggle-active")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_toggle_user_active_forbidden(client: AsyncClient) -> None:
    """Non-admin receives 403."""
    user = _make_user(is_admin=False)
    with override_current_user(user):
        resp = await client.post(f"/api/v1/admin/users/{uuid.uuid4()}/toggle-active")
    assert resp.status_code == 403


# ── GET /admin/feedback ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_feedback_success(client: AsyncClient) -> None:
    """Admin receives paginated feedback list."""
    admin = _make_user(is_admin=True)
    feedback_items = [_make_feedback_resp() for _ in range(3)]

    with (
        override_current_user(admin),
        patch(
            "app.api.v1.admin.admin_service.list_feedback",
            new=AsyncMock(return_value=(feedback_items, 3)),
        ),
    ):
        resp = await client.get("/api/v1/admin/feedback")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["data"]) == 3


@pytest.mark.asyncio
async def test_list_feedback_unread_only(client: AsyncClient) -> None:
    """unread_only=true is forwarded to the service."""
    admin = _make_user(is_admin=True)

    with (
        override_current_user(admin),
        patch(
            "app.api.v1.admin.admin_service.list_feedback",
            new=AsyncMock(return_value=([], 0)),
        ) as mock_fb,
    ):
        resp = await client.get("/api/v1/admin/feedback?unread_only=true")

    assert resp.status_code == 200
    _, kwargs = mock_fb.call_args
    assert kwargs["unread_only"] is True


@pytest.mark.asyncio
async def test_list_feedback_forbidden(client: AsyncClient) -> None:
    """Non-admin receives 403."""
    user = _make_user(is_admin=False)
    with override_current_user(user):
        resp = await client.get("/api/v1/admin/feedback")
    assert resp.status_code == 403


# ── POST /admin/feedback/{id}/mark-read ───────────────────────────────────


@pytest.mark.asyncio
async def test_mark_feedback_read_success(client: AsyncClient) -> None:
    """Admin marks a feedback item as read."""
    admin = _make_user(is_admin=True)
    fb_id = uuid.uuid4()
    fb = _make_feedback_resp(feedback_id=fb_id)

    with (
        override_current_user(admin),
        patch(
            "app.api.v1.admin.admin_service.mark_feedback_read",
            new=AsyncMock(return_value=fb),
        ),
    ):
        resp = await client.post(f"/api/v1/admin/feedback/{fb_id}/mark-read")

    assert resp.status_code == 200
    assert resp.json()["data"]["is_read"] is True


@pytest.mark.asyncio
async def test_mark_feedback_read_not_found(client: AsyncClient) -> None:
    """Returns 404 when feedback doesn't exist."""
    from app.core.exceptions import NotFoundError

    admin = _make_user(is_admin=True)

    with (
        override_current_user(admin),
        patch(
            "app.api.v1.admin.admin_service.mark_feedback_read",
            new=AsyncMock(side_effect=NotFoundError("Feedback")),
        ),
    ):
        resp = await client.post(f"/api/v1/admin/feedback/{uuid.uuid4()}/mark-read")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_mark_feedback_read_forbidden(client: AsyncClient) -> None:
    """Non-admin receives 403."""
    user = _make_user(is_admin=False)
    with override_current_user(user):
        resp = await client.post(f"/api/v1/admin/feedback/{uuid.uuid4()}/mark-read")
    assert resp.status_code == 403
