"""Tag endpoint tests.

Coverage:
- GET  /api/v1/tags            — list, unauthenticated
- POST /api/v1/tags            — create, duplicate name (conflict), validation
- GET  /api/v1/tags/{id}       — found, not found, unauthenticated
- PATCH /api/v1/tags/{id}      — rename, duplicate name (conflict)
- DELETE /api/v1/tags/{id}     — delete, not found, unauthenticated
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import override_current_user


def _make_user(**kwargs: Any) -> Any:
    from unittest.mock import MagicMock

    user = MagicMock()
    user.id = kwargs.get("id", uuid.uuid4())
    user.is_active = True
    return user


def _make_tag_response(name: str = "bugfix", user_id: uuid.UUID | None = None) -> Any:
    from app.schemas.tags import TagResponse

    return TagResponse(
        id=uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        name=name,
        created_at=datetime.now(UTC),
    )


# ── GET /tags ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_tags_success(client: AsyncClient) -> None:
    user = _make_user()
    tags = [_make_tag_response("bugfix"), _make_tag_response("feature")]

    with (
        override_current_user(user),
        patch("app.services.tags.list_tags", new_callable=AsyncMock) as mock_list,
    ):
        mock_list.return_value = tags
        resp = await client.get("/api/v1/tags")

    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 2


@pytest.mark.asyncio
async def test_list_tags_unauthenticated(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/tags")
    assert resp.status_code == 401


# ── POST /tags ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_tag_success(client: AsyncClient) -> None:
    user = _make_user()
    new_tag = _make_tag_response("bugfix")

    with (
        override_current_user(user),
        patch("app.services.tags.create_tag", new_callable=AsyncMock) as mock_create,
    ):
        mock_create.return_value = new_tag
        resp = await client.post("/api/v1/tags", json={"name": "bugfix"})

    assert resp.status_code == 201
    assert resp.json()["data"]["name"] == "bugfix"


@pytest.mark.asyncio
async def test_create_tag_duplicate(client: AsyncClient) -> None:
    from app.core.exceptions import ConflictError

    user = _make_user()

    with (
        override_current_user(user),
        patch("app.services.tags.create_tag", new_callable=AsyncMock) as mock_create,
    ):
        mock_create.side_effect = ConflictError("Tag named 'bugfix' already exists")
        resp = await client.post("/api/v1/tags", json={"name": "bugfix"})

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_tag_validation_error(client: AsyncClient) -> None:
    user = _make_user()

    with override_current_user(user):
        resp = await client.post("/api/v1/tags", json={})  # missing name
    assert resp.status_code == 422

    with override_current_user(user):
        # name too long (max 50)
        resp = await client.post("/api/v1/tags", json={"name": "x" * 51})
    assert resp.status_code == 422


# ── GET /tags/{tag_id} ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_tag_success(client: AsyncClient) -> None:
    user = _make_user()
    tag = _make_tag_response("feature")

    with (
        override_current_user(user),
        patch("app.services.tags.get_tag", new_callable=AsyncMock) as mock_get,
    ):
        mock_get.return_value = tag
        resp = await client.get(f"/api/v1/tags/{tag.id}")

    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "feature"


@pytest.mark.asyncio
async def test_get_tag_not_found(client: AsyncClient) -> None:
    from app.core.exceptions import NotFoundError

    user = _make_user()

    with (
        override_current_user(user),
        patch("app.services.tags.get_tag", new_callable=AsyncMock) as mock_get,
    ):
        mock_get.side_effect = NotFoundError("Tag")
        resp = await client.get(f"/api/v1/tags/{uuid.uuid4()}")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_tag_unauthenticated(client: AsyncClient) -> None:
    resp = await client.get(f"/api/v1/tags/{uuid.uuid4()}")
    assert resp.status_code == 401


# ── PATCH /tags/{tag_id} ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_tag_success(client: AsyncClient) -> None:
    user = _make_user()
    updated_tag = _make_tag_response("renamed-tag")

    with (
        override_current_user(user),
        patch("app.services.tags.update_tag", new_callable=AsyncMock) as mock_update,
    ):
        mock_update.return_value = updated_tag
        resp = await client.patch(
            f"/api/v1/tags/{uuid.uuid4()}",
            json={"name": "renamed-tag"},
        )

    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "renamed-tag"


@pytest.mark.asyncio
async def test_update_tag_duplicate(client: AsyncClient) -> None:
    from app.core.exceptions import ConflictError

    user = _make_user()

    with (
        override_current_user(user),
        patch("app.services.tags.update_tag", new_callable=AsyncMock) as mock_update,
    ):
        mock_update.side_effect = ConflictError("Tag named 'feature' already exists")
        resp = await client.patch(
            f"/api/v1/tags/{uuid.uuid4()}",
            json={"name": "feature"},
        )

    assert resp.status_code == 409


# ── DELETE /tags/{tag_id} ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_tag_success(client: AsyncClient) -> None:
    user = _make_user()

    with (
        override_current_user(user),
        patch("app.services.tags.delete_tag", new_callable=AsyncMock) as mock_delete,
    ):
        mock_delete.return_value = None
        resp = await client.delete(f"/api/v1/tags/{uuid.uuid4()}")

    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_delete_tag_not_found(client: AsyncClient) -> None:
    from app.core.exceptions import NotFoundError

    user = _make_user()

    with (
        override_current_user(user),
        patch("app.services.tags.delete_tag", new_callable=AsyncMock) as mock_delete,
    ):
        mock_delete.side_effect = NotFoundError("Tag")
        resp = await client.delete(f"/api/v1/tags/{uuid.uuid4()}")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_tag_unauthenticated(client: AsyncClient) -> None:
    resp = await client.delete(f"/api/v1/tags/{uuid.uuid4()}")
    assert resp.status_code == 401
