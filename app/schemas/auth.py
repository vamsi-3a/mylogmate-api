"""Auth request/response schemas.

Rules:
- Never expose password_hash, refresh_token_hash, or google_id in responses.
- access_token returned in response body; refresh token is set as httpOnly cookie
  by the route handler (not part of this schema).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# ── Request schemas ───────────────────────────────────────────────────────


class SignupRequest(BaseModel):
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_]+$",
        description="Alphanumeric + underscore only",
    )
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class GoogleAuthRequest(BaseModel):
    """Google OAuth — frontend sends the ID token from Google Sign-In."""

    id_token: str = Field(..., min_length=1)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1, description="JWT reset token from email link")
    new_password: str = Field(..., min_length=8, max_length=128)


class UpdateProfileRequest(BaseModel):
    """Partial update — only provided fields are changed."""

    username: str | None = Field(
        default=None,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_]+$",
    )
    email: EmailStr | None = None


class UpdatePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def new_differs_from_current(cls, v: str, info: object) -> str:
        # Avoid accepting identical passwords silently
        current = getattr(info, "data", {}).get("current_password")
        if current and v == current:
            raise ValueError("New password must differ from current password")
        return v


# ── Response schemas ───────────────────────────────────────────────────────


class UserResponse(BaseModel):
    """Public user profile — safe to return in API responses."""

    id: uuid.UUID
    username: str
    email: str | None
    auth_provider: str
    is_admin: bool
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """Returned on successful login/signup/oauth/refresh.

    access_token: short-lived JWT (15 min) — stored in Zustand memory.
    Refresh token is set as an httpOnly cookie by the route handler.
    """

    access_token: str
    token_type: str = "bearer"
    user: UserResponse
