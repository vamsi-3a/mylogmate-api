"""Auth endpoint tests.

All DB and external calls are mocked — no real PostgreSQL, Redis, or Google required.

Coverage:
- POST /api/v1/auth/signup      — happy path, duplicate user, validation
- POST /api/v1/auth/login       — happy path, wrong password, inactive user
- POST /api/v1/auth/google      — happy path (mocked token verification)
- POST /api/v1/auth/refresh     — happy path, missing cookie, revoked token
- POST /api/v1/auth/logout      — happy path, unauthenticated
- POST /api/v1/auth/forgot-password  — always 200
- POST /api/v1/auth/reset-password   — happy path, invalid token
- GET  /api/v1/auth/me          — happy path, unauthenticated
- PATCH /api/v1/auth/me         — update username
- POST /api/v1/auth/me/password — change password, wrong current password
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import override_current_user

# ── Shared helpers ────────────────────────────────────────────────────────


def _make_user(**kwargs: Any) -> MagicMock:
    """Return a mock User ORM object with sensible defaults."""
    user = MagicMock()
    user.id = kwargs.get("id", uuid.uuid4())
    user.username = kwargs.get("username", "testuser")
    user.email = kwargs.get("email", "test@example.com")
    user.password_hash = kwargs.get(
        "password_hash",
        "$2b$12$placeholder_hash_for_testing_purposes_only",
    )
    user.google_id = kwargs.get("google_id", None)
    user.auth_provider = kwargs.get("auth_provider", "local")
    user.refresh_token_hash = kwargs.get("refresh_token_hash", None)
    user.is_admin = kwargs.get("is_admin", False)
    user.is_active = kwargs.get("is_active", True)
    user.last_login_at = kwargs.get("last_login_at", None)
    user.created_at = kwargs.get("created_at", datetime.now(UTC))
    return user


# ── POST /auth/signup ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_signup_success(client: AsyncClient) -> None:
    """Signup returns 201 with access token and sets refresh cookie."""
    user = _make_user()

    from app.schemas.auth import TokenResponse, UserResponse

    token_response = TokenResponse(
        access_token="test.access.token",
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            auth_provider=user.auth_provider,
            is_admin=user.is_admin,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )

    with patch("app.services.auth.signup", new_callable=AsyncMock) as mock_signup:
        mock_signup.return_value = (token_response, "raw.refresh.token")

        resp = await client.post(
            "/api/v1/auth/signup",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "securepassword123",
            },
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert "access_token" in body["data"]
    assert body["data"]["token_type"] == "bearer"
    assert "refresh_token" in resp.cookies


@pytest.mark.asyncio
async def test_signup_duplicate_user(client: AsyncClient) -> None:
    """Signup returns 409 when username or email already exists."""
    from app.core.exceptions import ConflictError

    with patch("app.services.auth.signup", new_callable=AsyncMock) as mock_signup:
        mock_signup.side_effect = ConflictError("Username or email already in use")

        resp = await client.post(
            "/api/v1/auth/signup",
            json={
                "username": "existing",
                "email": "existing@example.com",
                "password": "securepassword123",
            },
        )

    assert resp.status_code == 409
    assert resp.json()["success"] is False


@pytest.mark.asyncio
async def test_signup_validation_error(client: AsyncClient) -> None:
    """Signup returns 422 for invalid input (password too short)."""
    resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "username": "u",  # too short (min 3)
            "email": "bad-email",
            "password": "short",  # too short (min 8)
        },
    )
    assert resp.status_code == 422


# ── POST /auth/login ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient) -> None:
    """Login returns 200 with tokens for valid credentials."""
    user = _make_user()
    from app.schemas.auth import TokenResponse, UserResponse

    token_response = TokenResponse(
        access_token="test.access.token",
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            auth_provider=user.auth_provider,
            is_admin=user.is_admin,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )

    with patch("app.services.auth.login", new_callable=AsyncMock) as mock_login:
        mock_login.return_value = (token_response, "raw.refresh.token")

        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "securepassword123"},
        )

    assert resp.status_code == 200
    assert resp.json()["data"]["access_token"] == "test.access.token"
    assert "refresh_token" in resp.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient) -> None:
    """Login returns 401 for wrong credentials."""
    from app.core.exceptions import UnauthorizedError

    with patch("app.services.auth.login", new_callable=AsyncMock) as mock_login:
        mock_login.side_effect = UnauthorizedError("Invalid username or password")

        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "wrongpassword"},
        )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user(client: AsyncClient) -> None:
    """Login returns 401 for deactivated accounts."""
    from app.core.exceptions import UnauthorizedError

    with patch("app.services.auth.login", new_callable=AsyncMock) as mock_login:
        mock_login.side_effect = UnauthorizedError("Account is disabled")

        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "inactive", "password": "password123"},
        )

    assert resp.status_code == 401


# ── POST /auth/google ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_google_auth_success(client: AsyncClient) -> None:
    """Google OAuth returns 200 with tokens for a valid ID token."""
    user = _make_user(auth_provider="google", google_id="google-sub-123")
    from app.schemas.auth import TokenResponse, UserResponse

    token_response = TokenResponse(
        access_token="test.access.token",
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            auth_provider=user.auth_provider,
            is_admin=user.is_admin,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )

    with patch("app.services.auth.google_auth", new_callable=AsyncMock) as mock_google:
        mock_google.return_value = (token_response, "raw.refresh.token")

        resp = await client.post(
            "/api/v1/auth/google",
            json={"id_token": "google.id.token.value"},
        )

    assert resp.status_code == 200
    assert resp.json()["data"]["access_token"] == "test.access.token"
    assert "refresh_token" in resp.cookies


@pytest.mark.asyncio
async def test_google_auth_invalid_token(client: AsyncClient) -> None:
    """Google OAuth returns 401 for an invalid ID token."""
    from app.core.exceptions import UnauthorizedError

    with patch("app.services.auth.google_auth", new_callable=AsyncMock) as mock_google:
        mock_google.side_effect = UnauthorizedError("Invalid Google ID token")

        resp = await client.post(
            "/api/v1/auth/google",
            json={"id_token": "bad.token"},
        )

    assert resp.status_code == 401


# ── POST /auth/refresh ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_success(client: AsyncClient) -> None:
    """Refresh rotates both tokens and sets new cookie."""
    user = _make_user()
    from app.schemas.auth import TokenResponse, UserResponse

    token_response = TokenResponse(
        access_token="new.access.token",
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            auth_provider=user.auth_provider,
            is_admin=user.is_admin,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )

    with patch("app.services.auth.refresh_tokens", new_callable=AsyncMock) as mock_refresh:
        mock_refresh.return_value = (token_response, "new.raw.refresh.token")

        resp = await client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": "old.raw.refresh.token"},
        )

    assert resp.status_code == 200
    assert resp.json()["data"]["access_token"] == "new.access.token"
    assert "refresh_token" in resp.cookies


@pytest.mark.asyncio
async def test_refresh_missing_cookie(client: AsyncClient) -> None:
    """Refresh returns 401 when no cookie is present."""
    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_revoked_token(client: AsyncClient) -> None:
    """Refresh returns 401 for a revoked refresh token."""
    from app.core.exceptions import UnauthorizedError

    with patch("app.services.auth.refresh_tokens", new_callable=AsyncMock) as mock_refresh:
        mock_refresh.side_effect = UnauthorizedError("Refresh token has been revoked")

        resp = await client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": "revoked.token"},
        )

    assert resp.status_code == 401


# ── POST /auth/logout ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_logout_success(client: AsyncClient) -> None:
    """Logout returns 200 and clears refresh cookie for authenticated user."""
    user = _make_user()

    with (
        override_current_user(user),
        patch("app.services.auth.logout", new_callable=AsyncMock),
    ):
        resp = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": "Bearer test.access.token"},
        )

    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_logout_unauthenticated(client: AsyncClient) -> None:
    """Logout returns 401 without a valid token."""
    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 401


# ── POST /auth/forgot-password ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_forgot_password_always_200(client: AsyncClient) -> None:
    """Forgot password always returns 200 regardless of whether email exists."""
    # Email exists
    with patch("app.services.auth.forgot_password", new_callable=AsyncMock) as mock_fp:
        mock_fp.return_value = "reset.token.value"
        resp = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "test@example.com"},
        )
    assert resp.status_code == 200

    # Email does NOT exist
    with patch("app.services.auth.forgot_password", new_callable=AsyncMock) as mock_fp:
        mock_fp.return_value = None
        resp = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nobody@example.com"},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_forgot_password_invalid_email(client: AsyncClient) -> None:
    """Forgot password returns 422 for non-email input."""
    resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "not-an-email"},
    )
    assert resp.status_code == 422


# ── POST /auth/reset-password ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reset_password_success(client: AsyncClient) -> None:
    """Reset password returns 200 for a valid token."""
    with patch("app.services.auth.reset_password", new_callable=AsyncMock) as mock_rp:
        mock_rp.return_value = None
        resp = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": "valid.reset.token", "new_password": "newpassword123"},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_invalid_token(client: AsyncClient) -> None:
    """Reset password returns 401 for an invalid/expired token."""
    from app.core.exceptions import UnauthorizedError

    with patch("app.services.auth.reset_password", new_callable=AsyncMock) as mock_rp:
        mock_rp.side_effect = UnauthorizedError("Invalid or expired reset token")
        resp = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": "bad.token", "new_password": "newpassword123"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_reset_password_weak_password(client: AsyncClient) -> None:
    """Reset password returns 422 if new_password is too short."""
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "some.token", "new_password": "short"},
    )
    assert resp.status_code == 422


# ── GET /auth/me ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_me_success(client: AsyncClient) -> None:
    """GET /me returns current user profile."""
    user = _make_user()

    with override_current_user(user):
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer test.access.token"},
        )

    assert resp.status_code == 200
    assert resp.json()["data"]["username"] == "testuser"


@pytest.mark.asyncio
async def test_me_unauthenticated(client: AsyncClient) -> None:
    """GET /me returns 401 without token."""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


# ── PATCH /auth/me ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_profile_success(client: AsyncClient) -> None:
    """PATCH /me updates username and returns new profile."""
    user = _make_user()
    updated_user = _make_user(username="newusername")

    from app.schemas.auth import UserResponse

    updated_response = UserResponse(
        id=updated_user.id,
        username="newusername",
        email=updated_user.email,
        auth_provider=updated_user.auth_provider,
        is_admin=updated_user.is_admin,
        is_active=updated_user.is_active,
        created_at=updated_user.created_at,
    )

    with (
        override_current_user(user),
        patch("app.services.auth.update_profile", new_callable=AsyncMock) as mock_up,
    ):
        mock_up.return_value = updated_response

        resp = await client.patch(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer test.access.token"},
            json={"username": "newusername"},
        )

    assert resp.status_code == 200
    assert resp.json()["data"]["username"] == "newusername"


# ── POST /auth/me/password ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_password_success(client: AsyncClient) -> None:
    """POST /me/password returns 200 for valid current password."""
    user = _make_user()

    with (
        override_current_user(user),
        patch("app.services.auth.update_password", new_callable=AsyncMock) as mock_pw,
    ):
        mock_pw.return_value = None

        resp = await client.post(
            "/api/v1/auth/me/password",
            headers={"Authorization": "Bearer test.access.token"},
            json={
                "current_password": "currentpassword",
                "new_password": "newpassword123",
            },
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_password_wrong_current(client: AsyncClient) -> None:
    """POST /me/password returns 422 when current password is wrong."""
    from app.core.exceptions import ValidationError

    user = _make_user()

    with (
        override_current_user(user),
        patch("app.services.auth.update_password", new_callable=AsyncMock) as mock_pw,
    ):
        mock_pw.side_effect = ValidationError("Current password is incorrect")

        resp = await client.post(
            "/api/v1/auth/me/password",
            headers={"Authorization": "Bearer test.access.token"},
            json={
                "current_password": "wrongcurrent",
                "new_password": "newpassword123",
            },
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_password_same_as_current(client: AsyncClient) -> None:
    """POST /me/password returns 422 when new == current (Pydantic validator)."""
    user = _make_user()

    with override_current_user(user):
        resp = await client.post(
            "/api/v1/auth/me/password",
            headers={"Authorization": "Bearer test.access.token"},
            json={
                "current_password": "samepassword",
                "new_password": "samepassword",
            },
        )

    assert resp.status_code == 422
