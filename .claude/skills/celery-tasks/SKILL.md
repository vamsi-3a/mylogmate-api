---
name: celery-tasks
description: Use when creating/modifying Celery tasks in app/workers/. Covers task structure, retry logic, error handling, and task registration. Trigger on any file in app/workers/ or when async background processing is needed.
---

# Celery Task Patterns

## Task Template
```python
from app.workers.celery_app import celery_app
import structlog

logger = structlog.get_logger()

@celery_app.task(bind=True, max_retries=3, default_retry_delay=30, acks_late=True)
def generate_and_store_embedding(self, log_entry_id: str) -> None:
    try:
        # 1. Fetch log entry from DB (sync session for Celery)
        # 2. Decrypt content
        # 3. Generate embedding vector
        # 4. Upsert to Qdrant with metadata
        logger.info("embedding_generated", log_entry_id=log_entry_id)
    except Exception as exc:
        logger.error("embedding_failed", log_entry_id=log_entry_id, error=str(exc))
        self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
```

## Celery App Configuration (app/workers/celery_app.py)
```python
from celery import Celery
from app.core.config import settings

celery_app = Celery("mylogmate", broker=settings.REDIS_URL)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_backend=None,  # We don't need result storage
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={"app.workers.embedding_tasks.*": {"queue": "embeddings"},
                 "app.workers.email_tasks.*": {"queue": "emails"}},
)
celery_app.autodiscover_tasks(["app.workers"])
```

## Rules
- bind=True for access to self (retries)
- acks_late=True so tasks aren't lost on worker crash
- Exponential backoff: countdown=30 * (2 ** self.request.retries)
- Max 3 retries per task
- Use structlog for task logging
- Celery tasks use SYNC database sessions (not async) — Celery workers don't run asyncio
- Dispatch tasks from services: `generate_and_store_embedding.delay(log_entry_id)`
- Never call .delay() from route handlers for tasks that must complete before response (use await for those)

## Current Tasks
- generate_and_store_embedding: After log create/edit
- delete_embedding: After log delete
- send_password_reset_email: After forgot-password request
