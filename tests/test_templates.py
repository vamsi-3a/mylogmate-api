"""Template endpoint tests.

All DB calls are mocked — no real PostgreSQL required.

Coverage:
- GET  /api/v1/templates            — list (includes samples + user templates),
                                      unauthenticated
- POST /api/v1/templates            — create, duplicate name, validation
- GET  /api/v1/templates/{id}       — found (sample), found (owned), not found,
                                      unauthenticated
- PATCH /api/v1/templates/{id}      — partial update (name), partial update (content),
                                      duplicate name, sample forbidden, not found
- DELETE /api/v1/templates/{id}     — delete, sample forbidden, not found,
                                      unauthenticated
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
    user.is_active = True
    return user


def _make_template_response(
    name: str = "Daily standup",
    is_sample: bool = False,
    user_id: uuid.UUID | None = None,
    category: str | None = None,
) -> Any:
    from app.schemas.templates import TemplateResponse

    return TemplateResponse(
        id=uuid.uuid4(),
        user_id=user_id,
        name=name,
        content="**Yesterday:**\n- \n\n**Today:**\n- ",
        is_sample=is_sample,
        category=category,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _create_payload(**kwargs: Any) -> dict[str, Any]:
    return {
        "name": kwargs.get("name", "My Template"),
        "content": kwargs.get("content", "Some template content"),
    }


# ── GET /templates ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_templates_success(client: AsyncClient) -> None:
    """Returns sample templates plus user's own templates."""
    user = _make_user()
    templates = [
        _make_template_response("Daily standup", is_sample=True),
        _make_template_response("My custom template", is_sample=False, user_id=user.id),
    ]

    with (
        override_current_user(user),
        patch(
            "app.services.templates.list_templates", new_callable=AsyncMock
        ) as mock_list,
    ):
        mock_list.return_value = templates
        resp = await client.get("/api/v1/templates")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert len(body["data"]) == 2
    # Sample template has no user_id
    sample = next(t for t in body["data"] if t["is_sample"])
    assert sample["user_id"] is None


@pytest.mark.asyncio
async def test_list_templates_empty(client: AsyncClient) -> None:
    """Returns empty list when no templates exist."""
    user = _make_user()

    with (
        override_current_user(user),
        patch(
            "app.services.templates.list_templates", new_callable=AsyncMock
        ) as mock_list,
    ):
        mock_list.return_value = []
        resp = await client.get("/api/v1/templates")

    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_list_templates_unauthenticated(client: AsyncClient) -> None:
    """Returns 401 without token."""
    resp = await client.get("/api/v1/templates")
    assert resp.status_code == 401


# ── POST /templates ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_template_success(client: AsyncClient) -> None:
    """Creates a personal template and returns 201."""
    user = _make_user()
    new_template = _make_template_response("My Template", is_sample=False, user_id=user.id)

    with (
        override_current_user(user),
        patch(
            "app.services.templates.create_template", new_callable=AsyncMock
        ) as mock_create,
    ):
        mock_create.return_value = new_template
        resp = await client.post("/api/v1/templates", json=_create_payload())

    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["is_sample"] is False


@pytest.mark.asyncio
async def test_create_template_duplicate(client: AsyncClient) -> None:
    """Returns 409 when a template with the same name already exists."""
    from app.core.exceptions import ConflictError

    user = _make_user()

    with (
        override_current_user(user),
        patch(
            "app.services.templates.create_template", new_callable=AsyncMock
        ) as mock_create,
    ):
        mock_create.side_effect = ConflictError("Template named 'My Template' already exists")
        resp = await client.post("/api/v1/templates", json=_create_payload())

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_template_missing_name(client: AsyncClient) -> None:
    """Returns 422 when name is missing."""
    user = _make_user()

    with override_current_user(user):
        resp = await client.post("/api/v1/templates", json={"content": "Some content"})

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_template_name_too_long(client: AsyncClient) -> None:
    """Returns 422 when name exceeds 100 chars."""
    user = _make_user()

    with override_current_user(user):
        resp = await client.post(
            "/api/v1/templates",
            json=_create_payload(name="x" * 101),
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_template_content_too_long(client: AsyncClient) -> None:
    """Returns 422 when content exceeds 5000 chars."""
    user = _make_user()

    with override_current_user(user):
        resp = await client.post(
            "/api/v1/templates",
            json=_create_payload(content="x" * 5001),
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_template_unauthenticated(client: AsyncClient) -> None:
    """Returns 401 without token."""
    resp = await client.post("/api/v1/templates", json=_create_payload())
    assert resp.status_code == 401


# ── GET /templates/{template_id} ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_template_sample(client: AsyncClient) -> None:
    """Returns a sample template (user_id=None, is_sample=True)."""
    user = _make_user()
    template = _make_template_response("Daily standup", is_sample=True, category="software_engineer")

    with (
        override_current_user(user),
        patch(
            "app.services.templates.get_template", new_callable=AsyncMock
        ) as mock_get,
    ):
        mock_get.return_value = template
        resp = await client.get(f"/api/v1/templates/{template.id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["is_sample"] is True
    assert body["data"]["user_id"] is None
    assert body["data"]["category"] == "software_engineer"


@pytest.mark.asyncio
async def test_get_template_owned(client: AsyncClient) -> None:
    """Returns a user-owned template."""
    user = _make_user()
    template = _make_template_response("My Template", is_sample=False, user_id=user.id)

    with (
        override_current_user(user),
        patch(
            "app.services.templates.get_template", new_callable=AsyncMock
        ) as mock_get,
    ):
        mock_get.return_value = template
        resp = await client.get(f"/api/v1/templates/{template.id}")

    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "My Template"


@pytest.mark.asyncio
async def test_get_template_not_found(client: AsyncClient) -> None:
    """Returns 404 when template doesn't exist or belongs to another user."""
    from app.core.exceptions import NotFoundError

    user = _make_user()

    with (
        override_current_user(user),
        patch(
            "app.services.templates.get_template", new_callable=AsyncMock
        ) as mock_get,
    ):
        mock_get.side_effect = NotFoundError("Template")
        resp = await client.get(f"/api/v1/templates/{uuid.uuid4()}")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_template_unauthenticated(client: AsyncClient) -> None:
    """Returns 401 without token."""
    resp = await client.get(f"/api/v1/templates/{uuid.uuid4()}")
    assert resp.status_code == 401


# ── PATCH /templates/{template_id} ────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_template_name(client: AsyncClient) -> None:
    """Partially updates the name and returns updated template."""
    user = _make_user()
    updated = _make_template_response("Renamed Template", is_sample=False, user_id=user.id)

    with (
        override_current_user(user),
        patch(
            "app.services.templates.update_template", new_callable=AsyncMock
        ) as mock_update,
    ):
        mock_update.return_value = updated
        resp = await client.patch(
            f"/api/v1/templates/{uuid.uuid4()}",
            json={"name": "Renamed Template"},
        )

    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Renamed Template"


@pytest.mark.asyncio
async def test_update_template_content(client: AsyncClient) -> None:
    """Partially updates content only."""
    user = _make_user()
    updated = _make_template_response("My Template", is_sample=False, user_id=user.id)
    updated.content = "Updated content here"  # type: ignore[attr-defined]

    with (
        override_current_user(user),
        patch(
            "app.services.templates.update_template", new_callable=AsyncMock
        ) as mock_update,
    ):
        mock_update.return_value = updated
        resp = await client.patch(
            f"/api/v1/templates/{uuid.uuid4()}",
            json={"content": "Updated content here"},
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_template_duplicate_name(client: AsyncClient) -> None:
    """Returns 409 when renaming to an existing template name."""
    from app.core.exceptions import ConflictError

    user = _make_user()

    with (
        override_current_user(user),
        patch(
            "app.services.templates.update_template", new_callable=AsyncMock
        ) as mock_update,
    ):
        mock_update.side_effect = ConflictError("Template named 'Daily standup' already exists")
        resp = await client.patch(
            f"/api/v1/templates/{uuid.uuid4()}",
            json={"name": "Daily standup"},
        )

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_update_template_sample_forbidden(client: AsyncClient) -> None:
    """Returns 403 when trying to modify a sample template."""
    from app.core.exceptions import ForbiddenError

    user = _make_user()

    with (
        override_current_user(user),
        patch(
            "app.services.templates.update_template", new_callable=AsyncMock
        ) as mock_update,
    ):
        mock_update.side_effect = ForbiddenError("Sample templates cannot be modified")
        resp = await client.patch(
            f"/api/v1/templates/{uuid.uuid4()}",
            json={"name": "New name"},
        )

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_template_not_found(client: AsyncClient) -> None:
    """Returns 404 when template doesn't exist."""
    from app.core.exceptions import NotFoundError

    user = _make_user()

    with (
        override_current_user(user),
        patch(
            "app.services.templates.update_template", new_callable=AsyncMock
        ) as mock_update,
    ):
        mock_update.side_effect = NotFoundError("Template")
        resp = await client.patch(
            f"/api/v1/templates/{uuid.uuid4()}",
            json={"name": "New name"},
        )

    assert resp.status_code == 404


# ── DELETE /templates/{template_id} ───────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_template_success(client: AsyncClient) -> None:
    """Deletes a user-owned template and returns 200."""
    user = _make_user()

    with (
        override_current_user(user),
        patch(
            "app.services.templates.delete_template", new_callable=AsyncMock
        ) as mock_delete,
    ):
        mock_delete.return_value = None
        resp = await client.delete(f"/api/v1/templates/{uuid.uuid4()}")

    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_delete_template_sample_forbidden(client: AsyncClient) -> None:
    """Returns 403 when trying to delete a sample template."""
    from app.core.exceptions import ForbiddenError

    user = _make_user()

    with (
        override_current_user(user),
        patch(
            "app.services.templates.delete_template", new_callable=AsyncMock
        ) as mock_delete,
    ):
        mock_delete.side_effect = ForbiddenError("Sample templates cannot be modified")
        resp = await client.delete(f"/api/v1/templates/{uuid.uuid4()}")

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_template_not_found(client: AsyncClient) -> None:
    """Returns 404 when template doesn't exist."""
    from app.core.exceptions import NotFoundError

    user = _make_user()

    with (
        override_current_user(user),
        patch(
            "app.services.templates.delete_template", new_callable=AsyncMock
        ) as mock_delete,
    ):
        mock_delete.side_effect = NotFoundError("Template")
        resp = await client.delete(f"/api/v1/templates/{uuid.uuid4()}")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_template_unauthenticated(client: AsyncClient) -> None:
    """Returns 401 without token."""
    resp = await client.delete(f"/api/v1/templates/{uuid.uuid4()}")
    assert resp.status_code == 401
