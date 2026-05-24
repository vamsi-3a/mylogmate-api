"""Structured JSON logging setup using structlog.

Call setup_logging() once at application startup (in lifespan).

NEVER log: passwords, JWT tokens, decrypted content, full user prompts, encryption keys.
"""

import logging
import sys

import structlog


def setup_logging(debug: bool = False) -> None:
    """Configure structlog for structured JSON output.

    In debug mode: human-readable colored output.
    In production: JSON lines suitable for log aggregation (Papertrail, Datadog, etc.).
    """
    log_level = logging.DEBUG if debug else logging.INFO

    # Standard library logging config (for libraries that use stdlib logging)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Silence noisy libraries in non-debug mode
    if not debug:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("alembic").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    if debug:
        # Dev: colorized, human-readable
        processors: list[structlog.types.Processor] = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # Production: JSON lines
        processors = [
            *shared_processors,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
