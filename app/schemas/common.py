"""Shared Pydantic schemas used across the entire API.

ApiResponse — standard envelope for all single-item responses.
PaginatedResponse — envelope for paginated list responses.
ErrorResponse — structured error with optional field-level details.
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ── Response envelopes ────────────────────────────────────────────────────


class ApiResponse(BaseModel, Generic[T]):
    """Standard response wrapper for all API endpoints.

    Example:
        {"success": true, "message": "Log created", "data": {...}}
    """

    success: bool = True
    message: str = ""
    data: T | None = None

    model_config = {"from_attributes": True}


class PaginatedResponse(BaseModel, Generic[T]):
    """Response wrapper for paginated list endpoints.

    Example:
        {"success": true, "data": [...], "total": 100, "page": 1, "page_size": 20}
    """

    success: bool = True
    message: str = ""
    data: list[T] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20

    model_config = {"from_attributes": True}


class ErrorDetail(BaseModel):
    """Individual field-level validation error."""

    field: str
    message: str
    type: str


class ErrorResponse(BaseModel):
    """Structured error response for 4xx/5xx responses.

    Example:
        {"success": false, "message": "Validation failed", "error_code": "VALIDATION_ERROR", "details": [...]}
    """

    success: bool = False
    message: str
    error_code: str = ""
    details: list[ErrorDetail] = Field(default_factory=list)


# ── Health check schemas ───────────────────────────────────────────────────


class ServiceStatus(BaseModel):
    """Status of a single external service."""

    status: str  # "ok" | "error: <reason>"


class HealthResponse(BaseModel):
    """Response for GET /health — lightweight liveness check."""

    status: str = "ok"


class ReadyResponse(BaseModel):
    """Response for GET /ready — full dependency health check."""

    status: str  # "ready" | "degraded"
    checks: dict[str, Any]
