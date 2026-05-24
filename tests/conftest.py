"""Pytest configuration and shared fixtures.

Environment variables are set BEFORE any app imports so pydantic-settings
picks them up at Settings() instantiation time.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

# ── Test environment variables ─────────────────────────────────────────────
# Must be set before any app module is imported (Settings() reads at import time).
# Using setdefault so that real env vars (from CI secrets) take precedence.

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/mylogmate_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("QDRANT_API_KEY", "")

# JWT secret — minimum 32 chars for HS256
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-minimum-32-chars!")

# Valid Fernet key (32 random bytes, URL-safe base64 encoded, 44 chars with = padding)
# Generated with: from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())
os.environ.setdefault("ENCRYPTION_KEY", "ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg=")

os.environ.setdefault("GROQ_API_KEY", "test-groq-api-key")
os.environ.setdefault("LLM_PROVIDER", "groq")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-google-client-secret")
os.environ.setdefault("SMTP_HOST", "localhost")
os.environ.setdefault("SMTP_PORT", "1025")
os.environ.setdefault("SMTP_USER", "test@example.com")
os.environ.setdefault("SMTP_PASSWORD", "test-smtp-password")
os.environ.setdefault("CORS_ORIGINS", '["http://localhost:5173"]')

# ── Now import app ─────────────────────────────────────────────────────────

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user
from app.main import app

# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """Async HTTP test client bound to the FastAPI app (no real network)."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@contextmanager
def override_current_user(user: Any) -> Generator[None, None, None]:
    """Context manager that overrides the get_current_user FastAPI dependency.

    Usage:
        with override_current_user(mock_user):
            resp = await client.get("/api/v1/auth/me", ...)

    FastAPI's DI holds a direct reference to the dependency function, so
    unittest.mock.patch() on the route module name has no effect — we must
    use app.dependency_overrides instead.
    """
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_user, None)
