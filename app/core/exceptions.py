"""Custom exception classes and FastAPI exception handlers."""

import structlog
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = structlog.get_logger()


# ── Custom exception hierarchy ────────────────────────────────────────────


class AppError(Exception):
    """Base application error. Converts to a structured JSON error response."""

    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, resource: str = "Resource") -> None:
        super().__init__(f"{resource} not found", status.HTTP_404_NOT_FOUND)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Unauthorized") -> None:
        super().__init__(message, status.HTTP_401_UNAUTHORIZED)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden") -> None:
        super().__init__(message, status.HTTP_403_FORBIDDEN)


class ConflictError(AppError):
    def __init__(self, message: str = "Conflict") -> None:
        super().__init__(message, status.HTTP_409_CONFLICT)


class RateLimitError(AppError):
    def __init__(self, message: str = "Rate limit exceeded. Try again later.") -> None:
        super().__init__(message, status.HTTP_429_TOO_MANY_REQUESTS)


class ValidationError(AppError):
    def __init__(self, message: str = "Validation error") -> None:
        super().__init__(message, status.HTTP_422_UNPROCESSABLE_ENTITY)


class ServiceUnavailableError(AppError):
    def __init__(self, service: str = "Service") -> None:
        super().__init__(
            f"{service} is temporarily unavailable",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )


# ── Exception handlers (registered in app/main.py) ───────────────────────


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle our custom AppError and its subclasses."""
    logger.warning(
        "app_error",
        status_code=exc.status_code,
        message=exc.message,
        path=str(request.url.path),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.message, "data": None},
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Handle FastAPI/Starlette HTTPException with our response envelope."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail or "HTTP error",
            "data": None,
        },
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors with detailed field-level feedback."""
    errors = exc.errors()
    logger.info(
        "validation_error",
        path=str(request.url.path),
        error_count=len(errors),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": "Request validation failed",
            "data": None,
            "details": [
                {
                    "field": ".".join(str(loc) for loc in err["loc"]),
                    "message": err["msg"],
                    "type": err["type"],
                }
                for err in errors
            ],
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unexpected exceptions. Logs full traceback."""
    logger.exception(
        "unhandled_exception",
        path=str(request.url.path),
        method=request.method,
        error=str(exc),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "An internal server error occurred",
            "data": None,
        },
    )
