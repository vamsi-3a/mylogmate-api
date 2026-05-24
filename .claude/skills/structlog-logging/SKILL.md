---
name: structlog-logging
description: Use when adding logging to any module. Covers structured JSON logging with structlog, what to log, what NOT to log. Trigger when adding log statements or setting up logging configuration.
---

# Structured Logging Patterns

## Setup (app/core/logging.py)
```python
import structlog

def setup_logging():
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(),
    )
```

## Usage
```python
import structlog
logger = structlog.get_logger()

# In services
logger.info("log_entry_created", user_id=str(user.id), context_id=str(context.id))
logger.error("embedding_generation_failed", log_entry_id=str(entry.id), error=str(exc))

# In middleware (request logging)
logger.info("request", method=request.method, path=request.url.path, status=response.status_code, duration_ms=duration)
```

## What to Log
- API requests (method, path, status, duration)
- Auth events (login, signup, failed attempts, token refresh)
- Log entry CRUD operations (user_id, action)
- AI queries (user_id, context_id, prompt length, response latency, tokens used)
- Celery task lifecycle (start, success, failure, retry)
- Errors with full context

## NEVER Log
- Passwords or password hashes
- JWT tokens
- Decrypted log content
- Full user prompts (truncate to ~50 chars if needed)
- Encryption keys
