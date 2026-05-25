"""Task dispatch helper.

In normal (worker) mode this just enqueues the task to Redis — instant, the
separate Celery worker does the work.

In eager mode (single-service free deploy, CELERY_TASK_ALWAYS_EAGER=true) the
task body runs in-process. Each task calls asyncio.run() internally, which
cannot run on an already-running event loop — so we execute the (synchronous)
eager dispatch on a worker thread. That thread has no running loop, so the
task's asyncio.run() works, and the API's event loop is never blocked.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.config import settings


async def dispatch(task: Any, *args: Any) -> None:
    """Enqueue (worker mode) or run-in-thread (eager mode) a Celery task."""
    if settings.CELERY_TASK_ALWAYS_EAGER:
        await asyncio.to_thread(task.delay, *args)
    else:
        task.delay(*args)
