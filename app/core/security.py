"""Security utilities — AES-256 encryption, JWT, password hashing, Google OAuth.

Encryption functions are fully implemented here (used throughout the app).
JWT + OAuth functions are implemented in Step 5 (Auth System).

NEVER log: plaintext content, tokens, keys, passwords.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

# ── AES-256 Encryption (Fernet) ──────────────────────────────────────────
#
# Fernet = AES-128-CBC with HMAC-SHA256 + timestamp. The key is a URL-safe
# base64-encoded 32-byte random value. Generate with: make gen-key
#
# Usage:
#   encrypted = encrypt_content("my sensitive log entry")
#   plaintext = decrypt_content(encrypted)


def _get_fernet() -> Fernet:
    """Return Fernet cipher configured from settings.
    Imported lazily to avoid circular imports at module load time.
    """
    from app.core.config import settings

    return Fernet(settings.ENCRYPTION_KEY.encode())


def encrypt_content(plaintext: str) -> str:
    """Encrypt a string with AES-256 (Fernet). Returns base64-encoded ciphertext."""
    f = _get_fernet()
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_content(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted string. Raises ValueError on failure."""
    f = _get_fernet()
    try:
        return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt content — invalid key or corrupted data") from exc


# ── JWT (implemented in Step 5) ──────────────────────────────────────────


def create_access_token(user_id: str, username: str, is_admin: bool) -> str:
    """Create a short-lived JWT access token. Implemented in Step 5."""
    raise NotImplementedError("JWT implemented in Step 5")


def create_refresh_token(user_id: str) -> str:
    """Create a long-lived JWT refresh token. Implemented in Step 5."""
    raise NotImplementedError("JWT implemented in Step 5")


def decode_token(token: str) -> dict[str, object]:
    """Decode and validate a JWT token. Implemented in Step 5."""
    raise NotImplementedError("JWT implemented in Step 5")


# ── Password hashing (implemented in Step 5) ─────────────────────────────


def hash_password(plain_password: str) -> str:
    """bcrypt hash a password. Implemented in Step 5."""
    raise NotImplementedError("Password hashing implemented in Step 5")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a bcrypt password. Implemented in Step 5."""
    raise NotImplementedError("Password verification implemented in Step 5")


# ── Google OAuth (implemented in Step 5) ─────────────────────────────────


async def verify_google_token(id_token: str) -> dict[str, object]:
    """Verify a Google OAuth ID token and return claims. Implemented in Step 5."""
    raise NotImplementedError("Google OAuth implemented in Step 5")
