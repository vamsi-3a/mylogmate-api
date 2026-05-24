"""FastAPI application factory.

Wires together: middleware, CORS, exception handlers, routers, lifespan events.
Health endpoints live here (no /api/v1 prefix — they're infrastructure endpoints).
"""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler  # type: ignore[attr-defined]
from slowapi.errors import RateLimitExceeded  # type: ignore[import-untyped]
from slowapi.util import get_remote_address  # type: ignore[import-untyped]
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings
from app.core.exceptions import (
    AppError,
    app_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import setup_logging
from app.db.session import AsyncSessionLocal, engine
from app.schemas.common import HealthResponse, ReadyResponse

logger = structlog.get_logger()


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle: setup before yield, teardown after yield."""
    # ── Startup ──────────────────────────────────────────────────────────
    setup_logging(debug=settings.DEBUG)
    logger.info(
        "startup",
        env=settings.APP_ENV,
        debug=settings.DEBUG,
        version=app.version,
    )

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    await engine.dispose()
    logger.info("shutdown")


# ── App factory ───────────────────────────────────────────────────────────


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="MyLogMate API",
        description=(
            "Work-logging + AI-recall backend. "
            "Log your work, tag it, and query with AI for performance reviews."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── Rate limiter (slowapi) ────────────────────────────────────────────
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(
        RateLimitExceeded, _rate_limit_exceeded_handler  # type: ignore[arg-type]
    )

    # ── Middleware (order matters: outer → inner) ──────────────────────────
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,  # Required for httpOnly cookie (refresh token)
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)

    # ── Exception handlers ────────────────────────────────────────────────
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # ── Health endpoints (no /api/v1 prefix) ──────────────────────────────
    _register_health_routes(app)

    # ── API v1 routers (populated as steps complete) ───────────────────────
    _register_api_routers(app)

    return app


# ── Request logging middleware ────────────────────────────────────────────


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request with method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000)

        # Skip logging health endpoints to reduce noise
        if request.url.path not in ("/health", "/ready"):
            logger.info(
                "http_request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=duration_ms,
            )

        return response


# ── Health endpoints ──────────────────────────────────────────────────────


def _register_health_routes(app: FastAPI) -> None:
    """Register /health and /ready endpoints directly on the app."""

    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["health"],
        summary="Liveness check — is the process running?",
    )
    async def health() -> HealthResponse:
        """Lightweight liveness probe. Used by Render to detect crashes.
        Always returns 200 if the process is alive.
        """
        return HealthResponse(status="ok")

    @app.get(
        "/ready",
        response_model=ReadyResponse,
        tags=["health"],
        summary="Readiness check — are all dependencies reachable?",
    )
    async def ready() -> JSONResponse:
        """Full dependency health check. Returns 200 if all services are up,
        503 (degraded) if any service is unreachable.

        Checks: PostgreSQL, Redis, Qdrant.
        """
        checks: dict[str, str] = {}

        # ── PostgreSQL ────────────────────────────────────────────────
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
            checks["postgresql"] = "ok"
        except Exception as exc:
            checks["postgresql"] = f"error: {exc}"
            logger.warning("readiness_check_failed", service="postgresql", error=str(exc))

        # ── Redis ─────────────────────────────────────────────────────
        try:
            import redis.asyncio as aioredis  # type: ignore[import-untyped]

            r: Any = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=3)
            await r.ping()
            await r.aclose()
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"error: {exc}"
            logger.warning("readiness_check_failed", service="redis", error=str(exc))

        # ── Qdrant ────────────────────────────────────────────────────
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{settings.QDRANT_URL}/readyz")
                checks["qdrant"] = "ok" if resp.status_code == 200 else f"http_{resp.status_code}"
        except Exception as exc:
            checks["qdrant"] = f"error: {exc}"
            logger.warning("readiness_check_failed", service="qdrant", error=str(exc))

        all_ok = all(v == "ok" for v in checks.values())
        status_code = 200 if all_ok else 503

        return JSONResponse(
            status_code=status_code,
            content={
                "status": "ready" if all_ok else "degraded",
                "checks": checks,
            },
        )


# ── API router registration ───────────────────────────────────────────────


def _register_api_routers(app: FastAPI) -> None:
    """Include all API v1 routers. Populated as implementation steps complete.

    Convention: all routers mount under /api/v1/<resource>
    """
    # Step 5: auth
    # from app.api.v1.auth import router as auth_router
    # app.include_router(auth_router, prefix="/api/v1")

    # Step 6: contexts
    # from app.api.v1.contexts import router as contexts_router
    # app.include_router(contexts_router, prefix="/api/v1")

    # Step 7: tags
    # from app.api.v1.tags import router as tags_router
    # app.include_router(tags_router, prefix="/api/v1")

    # Step 8: logs
    # from app.api.v1.logs import router as logs_router
    # app.include_router(logs_router, prefix="/api/v1")

    # Step 9: templates
    # from app.api.v1.templates import router as templates_router
    # app.include_router(templates_router, prefix="/api/v1")

    # Step 14: recall
    # from app.api.v1.recall import router as recall_router
    # app.include_router(recall_router, prefix="/api/v1")

    # Step 16: admin
    # from app.api.v1.admin import router as admin_router
    # app.include_router(admin_router, prefix="/api/v1")

    # Step 17: feedback
    # from app.api.v1.feedback import router as feedback_router
    # app.include_router(feedback_router, prefix="/api/v1")

    pass  # Remove this when first router is registered


# ── Application instance ─────────────────────────────────────────────────

app = create_app()
