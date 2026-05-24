"""Calendar endpoint tests.

Coverage:
- GET /api/v1/logs/calendar/{year}/{month}
  — success (all days, some with entries)
  — success filtered by context_id
  — context not found (404)
  — invalid year / invalid month (422)
  — unauthenticated (401)
"""

from __future__ import annotations

import uuid
from datetime import date
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


def _make_calendar_response(year: int = 2026, month: int = 5) -> Any:
    """Build a CalendarMonthResponse with a couple of days having entries."""
    import calendar as cal_mod

    from app.schemas.logs import CalendarDayResponse, CalendarMonthResponse

    _, days_in_month = cal_mod.monthrange(year, month)
    days = [
        CalendarDayResponse(
            date=date(year, month, d),
            log_count=2 if d in (1, 15) else 0,
            has_entries=d in (1, 15),
        )
        for d in range(1, days_in_month + 1)
    ]
    return CalendarMonthResponse(year=year, month=month, days=days)


# ── Tests ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_calendar_success(client: AsyncClient) -> None:
    """Returns a full month of CalendarDayResponse entries."""
    user = _make_user()
    cal = _make_calendar_response(2026, 5)

    with (
        override_current_user(user),
        patch("app.services.logs.get_calendar", new_callable=AsyncMock) as mock_cal,
    ):
        mock_cal.return_value = cal
        resp = await client.get("/api/v1/logs/calendar/2026/5")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["year"] == 2026
    assert data["month"] == 5
    # May has 31 days
    assert len(data["days"]) == 31
    # Days 1 and 15 have entries
    day_1 = next(d for d in data["days"] if d["date"] == "2026-05-01")
    assert day_1["has_entries"] is True
    assert day_1["log_count"] == 2
    # Day 3 has no entries
    day_3 = next(d for d in data["days"] if d["date"] == "2026-05-03")
    assert day_3["has_entries"] is False
    assert day_3["log_count"] == 0


@pytest.mark.asyncio
async def test_calendar_with_context_id(client: AsyncClient) -> None:
    """Passes context_id to the service for filtering."""
    user = _make_user()
    context_id = uuid.uuid4()
    cal = _make_calendar_response(2026, 5)

    with (
        override_current_user(user),
        patch("app.services.logs.get_calendar", new_callable=AsyncMock) as mock_cal,
    ):
        mock_cal.return_value = cal
        resp = await client.get(
            "/api/v1/logs/calendar/2026/5",
            params={"context_id": str(context_id)},
        )

    assert resp.status_code == 200
    # Verify the service was called with context_id
    assert mock_cal.call_args.kwargs["context_id"] == context_id


@pytest.mark.asyncio
async def test_calendar_context_not_found(client: AsyncClient) -> None:
    """Returns 404 when context_id doesn't belong to the user."""
    from app.core.exceptions import NotFoundError

    user = _make_user()

    with (
        override_current_user(user),
        patch("app.services.logs.get_calendar", new_callable=AsyncMock) as mock_cal,
    ):
        mock_cal.side_effect = NotFoundError("Context")
        resp = await client.get(
            "/api/v1/logs/calendar/2026/5",
            params={"context_id": str(uuid.uuid4())},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_calendar_february_days(client: AsyncClient) -> None:
    """Returns 28 days for February in a non-leap year."""
    user = _make_user()
    cal = _make_calendar_response(2025, 2)  # 2025 is not a leap year

    with (
        override_current_user(user),
        patch("app.services.logs.get_calendar", new_callable=AsyncMock) as mock_cal,
    ):
        mock_cal.return_value = cal
        resp = await client.get("/api/v1/logs/calendar/2025/2")

    assert resp.status_code == 200
    assert len(resp.json()["data"]["days"]) == 28


@pytest.mark.asyncio
async def test_calendar_invalid_month_zero(client: AsyncClient) -> None:
    """Returns 422 when month is 0."""
    user = _make_user()

    with override_current_user(user):
        resp = await client.get("/api/v1/logs/calendar/2026/0")

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_calendar_invalid_month_thirteen(client: AsyncClient) -> None:
    """Returns 422 when month is 13."""
    user = _make_user()

    with override_current_user(user):
        resp = await client.get("/api/v1/logs/calendar/2026/13")

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_calendar_invalid_year_too_low(client: AsyncClient) -> None:
    """Returns 422 when year is below 2000."""
    user = _make_user()

    with override_current_user(user):
        resp = await client.get("/api/v1/logs/calendar/1999/5")

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_calendar_invalid_year_too_high(client: AsyncClient) -> None:
    """Returns 422 when year exceeds 2100."""
    user = _make_user()

    with override_current_user(user):
        resp = await client.get("/api/v1/logs/calendar/2101/5")

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_calendar_unauthenticated(client: AsyncClient) -> None:
    """Returns 401 without a token."""
    resp = await client.get("/api/v1/logs/calendar/2026/5")
    assert resp.status_code == 401
