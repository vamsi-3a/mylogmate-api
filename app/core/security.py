"""Security utilities — AES-256 encryption, JWT, password hashing, Google OAuth.

NEVER log: plaintext content, tokens, keys, passwords, or decrypted data.

Token types in JWT 'type' claim:
  'access'  — short-lived (ACCESS_TOKEN_EXPIRE_MINUTES)
  'refresh' — long-lived (REFRESH_TOKEN_EXPIRE_DAYS)
  'reset'   — one-time password-reset link (15 minutes)
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from cryptography.fernet import Fernet, InvalidToken
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

# ── AES-256 Encryption (Fernet) ──────────────────────────────────────────
#
# Fernet = AES-128-CBC with HMAC-SHA256 + timestamp.
# Key is a URL-safe base64-encoded 32-byte random value.
# Generate with: make gen-key


def _get_fernet() -> Fernet:
    """Return Fernet cipher configured from settings (lazy to avoid circular imports)."""
    from app.core.config import settings

    return Fernet(settings.ENCRYPTION_KEY.encode())


def encrypt_content(plaintext: str) -> str:
    """Encrypt a string with AES-256 (Fernet). Returns base64-encoded ciphertext."""
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_content(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted string. Raises ValueError on invalid data."""
    try:
        return _get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt — invalid key or corrupted data") from exc


# ── Password hashing (bcrypt) ─────────────────────────────────────────────


def hash_password(plain_password: str) -> str:
    """Return a bcrypt hash of the password. Cost factor=12."""
    import bcrypt

    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode(
        "utf-8"
    )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if plain_password matches the bcrypt hash."""
    import bcrypt

    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


# ── Refresh token hash ────────────────────────────────────────────────────


def hash_refresh_token(token: str) -> str:
    """SHA-256 hash a refresh token for storage in users.refresh_token_hash.

    We use SHA-256 (not bcrypt) here because:
    - The token itself is already a cryptographically random JWT — not a user-chosen secret
    - SHA-256 is fast; no need for bcrypt's slow KDF against dictionary attacks
    - We only need equality check (token_hash == stored_hash), not cracking resistance
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ── JWT ───────────────────────────────────────────────────────────────────


def _jwt_settings() -> tuple[str, str]:
    """Return (secret_key, algorithm) from settings."""
    from app.core.config import settings

    return settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM


def create_access_token(user_id: str, username: str, is_admin: bool) -> str:
    """Create a short-lived JWT access token (15 min by default)."""
    from app.core.config import settings

    secret, algorithm = _jwt_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "username": username,
        "is_admin": is_admin,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def create_refresh_token(user_id: str) -> str:
    """Create a long-lived JWT refresh token (7 days by default)."""
    from app.core.config import settings

    secret, algorithm = _jwt_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def create_reset_token(user_id: str) -> str:
    """Create a one-time password-reset JWT (15 minutes)."""
    secret, algorithm = _jwt_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "type": "reset",
        "iat": now,
        "exp": now + timedelta(minutes=15),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    """Decode and validate a JWT token.

    Args:
        token: Raw JWT string.
        expected_type: 'access' | 'refresh' | 'reset' — validated against 'type' claim.

    Returns:
        Decoded payload dict.

    Raises:
        jwt.ExpiredSignatureError: Token has expired.
        jwt.InvalidTokenError: Token is malformed or signature invalid.
        ValueError: 'type' claim does not match expected_type.
    """
    secret, algorithm = _jwt_settings()
    payload: dict[str, Any] = jwt.decode(token, secret, algorithms=[algorithm])
    if payload.get("type") != expected_type:
        raise ValueError(
            f"Invalid token type: expected '{expected_type}', got '{payload.get('type')}'"
        )
    return payload


# ── Google OAuth ──────────────────────────────────────────────────────────


async def verify_google_token(id_token: str) -> dict[str, Any]:
    """Verify a Google OAuth ID token and return the decoded claims.

    Returns dict with at minimum: 'sub' (google_id), 'email', 'name'.
    Raises ValueError if the token is invalid or the audience does not match.
    """
    from app.core.config import settings

    if not settings.GOOGLE_CLIENT_ID:
        raise ValueError("Google OAuth is not configured (GOOGLE_CLIENT_ID missing)")

    try:
        # google.oauth2.id_token.verify_oauth2_token is synchronous — run it
        # directly (it's a fast local JWT verification, not a network call).
        claims: dict[str, Any] = google_id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
            id_token,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except Exception as exc:
        raise ValueError(f"Invalid Google ID token: {exc}") from exc

    if "sub" not in claims or "email" not in claims:
        raise ValueError("Google token missing required claims (sub, email)")

    return claims
