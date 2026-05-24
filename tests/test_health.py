"""Tests for /health and /ready endpoints.

/health — always 200 (liveness, no external deps)
/ready  — 200 or 503 depending on service availability
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient

# ── /health ───────────────────────────────────────────────────────────────


async def test_health_returns_200(client: AsyncClient) -> None:
    """Liveness endpoint always returns 200 with status=ok."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


async def test_health_does_not_require_auth(client: AsyncClient) -> None:
    """Health endpoint is public — no auth header needed."""
    response = await client.get("/health")
    assert response.status_code == 200


# ── /ready (all services healthy) ─────────────────────────────────────────


async def test_ready_all_services_healthy(client: AsyncClient) -> None:
    """Ready endpoint returns 200 when all services respond correctly."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_session_factory = MagicMock(return_value=mock_session)

    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)
    mock_redis.aclose = AsyncMock()

    mock_http_response = MagicMock()
    mock_http_response.status_code = 200

    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(return_value=mock_http_response)
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.main.AsyncSessionLocal", mock_session_factory),
        patch("redis.asyncio.from_url", return_value=mock_redis),
        patch("httpx.AsyncClient", return_value=mock_http_client),
    ):
        response = await client.get("/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["postgresql"] == "ok"
    assert data["checks"]["redis"] == "ok"
    assert data["checks"]["qdrant"] == "ok"


# ── /ready (services unavailable) ─────────────────────────────────────────


async def test_ready_degraded_when_db_unavailable(client: AsyncClient) -> None:
    """Ready endpoint returns 503 when PostgreSQL is unreachable."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=ConnectionRefusedError("DB unavailable"))
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_session_factory = MagicMock(return_value=mock_session)

    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)
    mock_redis.aclose = AsyncMock()

    mock_http_response = MagicMock()
    mock_http_response.status_code = 200

    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(return_value=mock_http_response)
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.main.AsyncSessionLocal", mock_session_factory),
        patch("redis.asyncio.from_url", return_value=mock_redis),
        patch("httpx.AsyncClient", return_value=mock_http_client),
    ):
        response = await client.get("/ready")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    assert "error" in data["checks"]["postgresql"]
    assert data["checks"]["redis"] == "ok"


async def test_ready_graceful_when_all_services_down(client: AsyncClient) -> None:
    """Ready endpoint returns 503 gracefully (never 500) even if all services fail."""

    def raise_error(*args: object, **kwargs: object) -> None:
        raise ConnectionRefusedError("Service unavailable")

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=ConnectionRefusedError("DB down"))
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_session_factory = MagicMock(return_value=mock_session)

    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(side_effect=ConnectionRefusedError("Redis down"))
    mock_redis.aclose = AsyncMock()

    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(side_effect=ConnectionRefusedError("Qdrant down"))
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.main.AsyncSessionLocal", mock_session_factory),
        patch("redis.asyncio.from_url", return_value=mock_redis),
        patch("httpx.AsyncClient", return_value=mock_http_client),
    ):
        response = await client.get("/ready")

    # Must be 503, never 500
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    assert "checks" in data
    for service_status in data["checks"].values():
        assert "error" in service_status


# ── Response shape ────────────────────────────────────────────────────────


async def test_health_response_schema(client: AsyncClient) -> None:
    """Health response matches the HealthResponse schema."""
    response = await client.get("/health")
    data = response.json()
    assert set(data.keys()) == {"status"}


async def test_ready_response_schema(client: AsyncClient) -> None:
    """Ready response always contains 'status' and 'checks' keys."""
    response = await client.get("/ready")
    data = response.json()
    assert "status" in data
    assert "checks" in data
    assert isinstance(data["checks"], dict)
    assert set(data["checks"].keys()) == {"postgresql", "redis", "qdrant"}
