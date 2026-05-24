"""Context endpoint tests.

All DB calls are mocked — no real PostgreSQL required.

Coverage:
- GET  /api/v1/contexts            — list, unauthenticated
- POST /api/v1/contexts            — create teammate/project, create self (forbidden),
                                     duplicate name (conflict), validation error
- GET  /api/v1/contexts/{id}       — found, not found, unauthenticated
- PATCH /api/v1/contexts/{id}      — rename, rename self (forbidden), duplicate name
- DELETE /api/v1/contexts/{id}     — delete, delete self (forbidden), not found
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
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
    user.username = kwargs.get("username", "testuser")
    user.is_admin = kwargs.get("is_admin", False)
    user.is_active = kwargs.get("is_active", True)
    return user


def _make_context_response(
    context_type: str = "teammate",
    name: str = "Alice",
    user_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    from app.schemas.contexts import ContextResponse

    return ContextResponse(
        id=uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        type=context_type,
        name=name,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


# ── GET /contexts ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_contexts_success(client: AsyncClient) -> None:
    """Returns list of all contexts for the user."""
    user = _make_user()
    contexts = [
        _make_context_response("self", "Self"),
        _make_context_response("teammate", "Alice"),
        _make_context_response("project", "Backend API"),
    ]

    with (
        override_current_user(user),
        patch("app.services.contexts.list_contexts", new_callable=AsyncMock) as mock_list,
    ):
        mock_list.return_value = contexts
        resp = await client.get("/api/v1/contexts")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert len(body["data"]) == 3


@pytest.mark.asyncio
async def test_list_contexts_unauthenticated(client: AsyncClient) -> None:
    """Returns 401 without a valid token."""
    resp = await client.get("/api/v1/contexts")
    assert resp.status_code == 401


# ── POST /contexts ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_teammate_context(client: AsyncClient) -> None:
    """Creates a teammate context and returns 201."""
    user = _make_user()
    new_ctx = _make_context_response("teammate", "Alice")

    with (
        override_current_user(user),
        patch(
            "app.services.contexts.create_context", new_callable=AsyncMock
        ) as mock_create,
    ):
        mock_create.return_value = new_ctx
        resp = await client.post(
            "/api/v1/contexts",
            json={"type": "teammate", "name": "Alice"},
        )

    assert resp.status_code == 201
    assert resp.json()["data"]["type"] == "teammate"
    assert resp.json()["data"]["name"] == "Alice"


@pytest.mark.asyncio
async def test_create_project_context(client: AsyncClient) -> None:
    """Creates a project context and returns 201."""
    user = _make_user()
    new_ctx = _make_context_response("project", "Backend API")

    with (
        override_current_user(user),
        patch(
            "app.services.contexts.create_context", new_callable=AsyncMock
        ) as mock_create,
    ):
        mock_create.return_value = new_ctx
        resp = await client.post(
            "/api/v1/contexts",
            json={"type": "project", "name": "Backend API"},
        )

    assert resp.status_code == 201
    assert resp.json()["data"]["type"] == "project"


@pytest.mark.asyncio
async def test_create_self_context_forbidden(client: AsyncClient) -> None:
    """Creating a 'self' context returns 403 (enforced by service)."""
    from app.core.exceptions import ForbiddenError

    user = _make_user()

    with (
        override_current_user(user),
        patch(
            "app.services.contexts.create_context", new_callable=AsyncMock
        ) as mock_create,
    ):
        mock_create.side_effect = ForbiddenError(
            "The Self context is created automatically at signup"
        )
        resp = await client.post(
            "/api/v1/contexts",
            json={"type": "self", "name": "Self"},
        )

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_context_duplicate(client: AsyncClient) -> None:
    """Duplicate name within same type returns 409."""
    from app.core.exceptions import ConflictError

    user = _make_user()

    with (
        override_current_user(user),
        patch(
            "app.services.contexts.create_context", new_callable=AsyncMock
        ) as mock_create,
    ):
        mock_create.side_effect = ConflictError(
            "A teammate context named 'Alice' already exists"
        )
        resp = await client.post(
            "/api/v1/contexts",
            json={"type": "teammate", "name": "Alice"},
        )

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_context_validation_error(client: AsyncClient) -> None:
    """Returns 422 when required fields are missing or type is invalid."""
    user = _make_user()

    with override_current_user(user):
        # Missing name
        resp = await client.post(
            "/api/v1/contexts",
            json={"type": "teammate"},
        )
    assert resp.status_code == 422

    with override_current_user(user):
        # Invalid type
        resp = await client.post(
            "/api/v1/contexts",
            json={"type": "invalid", "name": "Test"},
        )
    assert resp.status_code == 422


# ── GET /contexts/{context_id} ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_context_success(client: AsyncClient) -> None:
    """Returns the context when found."""
    user = _make_user()
    ctx = _make_context_response("teammate", "Alice")
    context_id = ctx.id

    with (
        override_current_user(user),
        patch(
            "app.services.contexts.get_context", new_callable=AsyncMock
        ) as mock_get,
    ):
        mock_get.return_value = ctx
        resp = await client.get(f"/api/v1/contexts/{context_id}")

    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Alice"


@pytest.mark.asyncio
async def test_get_context_not_found(client: AsyncClient) -> None:
    """Returns 404 when context doesn't belong to the user."""
    from app.core.exceptions import NotFoundError

    user = _make_user()

    with (
        override_current_user(user),
        patch(
            "app.services.contexts.get_context", new_callable=AsyncMock
        ) as mock_get,
    ):
        mock_get.side_effect = NotFoundError("Context")
        resp = await client.get(f"/api/v1/contexts/{uuid.uuid4()}")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_context_unauthenticated(client: AsyncClient) -> None:
    """Returns 401 without token."""
    resp = await client.get(f"/api/v1/contexts/{uuid.uuid4()}")
    assert resp.status_code == 401


# ── PATCH /contexts/{context_id} ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_context_success(client: AsyncClient) -> None:
    """Renames a teammate context and returns updated response."""
    user = _make_user()
    updated_ctx = _make_context_response("teammate", "Bob")
    context_id = updated_ctx.id

    with (
        override_current_user(user),
        patch(
            "app.services.contexts.update_context", new_callable=AsyncMock
        ) as mock_update,
    ):
        mock_update.return_value = updated_ctx
        resp = await client.patch(
            f"/api/v1/contexts/{context_id}",
            json={"name": "Bob"},
        )

    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Bob"


@pytest.mark.asyncio
async def test_update_self_context_forbidden(client: AsyncClient) -> None:
    """Returns 403 when trying to rename the Self context."""
    from app.core.exceptions import ForbiddenError

    user = _make_user()

    with (
        override_current_user(user),
        patch(
            "app.services.contexts.update_context", new_callable=AsyncMock
        ) as mock_update,
    ):
        mock_update.side_effect = ForbiddenError("The Self context cannot be renamed")
        resp = await client.patch(
            f"/api/v1/contexts/{uuid.uuid4()}",
            json={"name": "NewName"},
        )

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_context_duplicate_name(client: AsyncClient) -> None:
    """Returns 409 when the new name collides with an existing context."""
    from app.core.exceptions import ConflictError

    user = _make_user()

    with (
        override_current_user(user),
        patch(
            "app.services.contexts.update_context", new_callable=AsyncMock
        ) as mock_update,
    ):
        mock_update.side_effect = ConflictError(
            "A teammate context named 'Alice' already exists"
        )
        resp = await client.patch(
            f"/api/v1/contexts/{uuid.uuid4()}",
            json={"name": "Alice"},
        )

    assert resp.status_code == 409


# ── DELETE /contexts/{context_id} ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_context_success(client: AsyncClient) -> None:
    """Deletes a context and returns 200."""
    user = _make_user()
    context_id = uuid.uuid4()

    with (
        override_current_user(user),
        patch(
            "app.services.contexts.delete_context", new_callable=AsyncMock
        ) as mock_delete,
    ):
        mock_delete.return_value = None
        resp = await client.delete(f"/api/v1/contexts/{context_id}")

    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_delete_self_context_forbidden(client: AsyncClient) -> None:
    """Returns 403 when trying to delete the Self context."""
    from app.core.exceptions import ForbiddenError

    user = _make_user()

    with (
        override_current_user(user),
        patch(
            "app.services.contexts.delete_context", new_callable=AsyncMock
        ) as mock_delete,
    ):
        mock_delete.side_effect = ForbiddenError("The Self context cannot be deleted")
        resp = await client.delete(f"/api/v1/contexts/{uuid.uuid4()}")

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_context_not_found(client: AsyncClient) -> None:
    """Returns 404 when context doesn't exist or belong to the user."""
    from app.core.exceptions import NotFoundError

    user = _make_user()

    with (
        override_current_user(user),
        patch(
            "app.services.contexts.delete_context", new_callable=AsyncMock
        ) as mock_delete,
    ):
        mock_delete.side_effect = NotFoundError("Context")
        resp = await client.delete(f"/api/v1/contexts/{uuid.uuid4()}")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_context_unauthenticated(client: AsyncClient) -> None:
    """Returns 401 without token."""
    resp = await client.delete(f"/api/v1/contexts/{uuid.uuid4()}")
    assert resp.status_code == 401
