---
path: app/workers/**
---
- Celery tasks use SYNC DB sessions (not async). Celery doesn't run asyncio.
- Always: bind=True, max_retries=3, acks_late=True
- Exponential backoff: countdown=30 * (2 ** self.request.retries)
- Log task lifecycle with structlog: start, success, failure
- Dispatch from services: task.delay(args). Never .delay() in route handlers.
