"""Shared rate limiter instance for slowapi.

Import the `limiter` from this module in all route files that need rate limiting.
The same instance must be registered in `app.state.limiter` in main.py.

Usage in route files:
    from fastapi import Request
    from app.core.rate_limit import limiter

    @router.post("/login")
    @limiter.limit("5/minute")
    async def login(request: Request, body: LoginRequest, ...) -> ...:
        ...

Note: The `request: Request` parameter is REQUIRED for slowapi to work — it
extracts the client IP from the request even if the handler doesn't use it.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
