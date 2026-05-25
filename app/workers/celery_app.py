"""Celery application configuration.

Two task queues:
    embeddings — log entry embed/delete tasks (Step 12)
    emails     — password reset email tasks (Step 12)

Workers are started with:
    celery -A app.workers.celery_app worker -l info -Q embeddings,emails

Rules (from .claude/rules/workers.md):
    - bind=True, max_retries=3, acks_late=True on all tasks
    - Exponential backoff: 30 * (2 ** retry_count) seconds
    - Sync DB sessions only (Celery doesn't run asyncio)
    - Log lifecycle events: start, success, failure
"""

from celery import Celery
from kombu import Exchange, Queue

from app.core.config import settings

# ── App ───────────────────────────────────────────────────────────────────

celery_app = Celery(
    "mylogmate",
    # Explicit task module imports so workers register them at startup.
    # Autodiscover would only find files named "tasks.py".
    include=[
        "app.workers.embedding_tasks",
        "app.workers.email_tasks",
    ],
)

# ── Configuration ─────────────────────────────────────────────────────────

celery_app.conf.update(
    # Broker & result backend
    broker_url=settings.REDIS_URL,
    result_backend=None,  # No result backend — fire-and-forget tasks

    # Eager mode — run tasks in-process instead of a separate worker.
    # Enabled for the single-service free deploy; harmless when False.
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_eager_propagates=False,  # a failed task never breaks the caller's request

    # Reliability
    task_acks_late=True,           # Ack only after task completes (safe on restart)
    task_reject_on_worker_lost=True,  # Re-queue if worker dies mid-task
    worker_prefetch_multiplier=1,  # Process one task at a time per worker

    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,

    # Queues
    task_queues=(
        Queue(
            "embeddings",
            Exchange("embeddings", type="direct"),
            routing_key="embeddings",
        ),
        Queue(
            "emails",
            Exchange("emails", type="direct"),
            routing_key="emails",
        ),
    ),
    task_default_queue="embeddings",
    task_routes={
        "app.workers.embedding_tasks.*": {"queue": "embeddings"},
        "app.workers.email_tasks.*": {"queue": "emails"},
    },

    # Retry defaults (individual tasks override these)
    task_max_retries=3,
    task_soft_time_limit=60,   # Warn after 60s
    task_time_limit=120,       # Kill after 120s (prevent hung tasks)

    # Beat schedule (future scheduled tasks — placeholder)
    beat_schedule={},
)

# Task modules are imported when workers start (autodiscover via explicit imports).
# Do NOT import task modules here — causes circular imports.
# Instead, each task file registers itself when loaded by the worker entrypoint.
