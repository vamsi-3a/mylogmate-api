"""Celery embedding tasks — async embedding lifecycle for log entries.

Task lifecycle:
  embed_log_entry       — triggered after create or update
  delete_log_embedding  — triggered after soft-delete

Rules (workers.md):
  - bind=True, max_retries=3, acks_late=True
  - Exponential backoff: countdown=30 * (2 ** retry_count)
  - Use asyncio.run() to call async DB/Qdrant code from the sync Celery context
  - Log start, success, and failure with structlog

DB access: async session via asyncio.run() (only asyncpg driver is installed).
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import structlog
from sqlalchemy import select

from app.ai.embeddings import generate_embedding
from app.ai.qdrant_store import delete_log_vector, upsert_log_vector
from app.core.security import decrypt_content
from app.db.models.log_entry import LogEntry
from app.db.session import AsyncSessionLocal
from app.workers.celery_app import celery_app

logger = structlog.get_logger()

# ── Async helpers (called via asyncio.run) ────────────────────────────────


async def _load_log_entry(log_id: uuid.UUID) -> LogEntry | None:
    """Load a non-deleted log entry from the DB."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(LogEntry).where(
                LogEntry.id == log_id,
                LogEntry.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()


async def _set_embedding_status(log_id: uuid.UUID, status: str) -> None:
    """Update the embedding_status field of a log entry."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(LogEntry).where(LogEntry.id == log_id)
        )
        entry = result.scalar_one_or_none()
        if entry is not None:
            entry.embedding_status = status
            await session.commit()


# ── Tasks ─────────────────────────────────────────────────────────────────


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="app.workers.embedding_tasks.embed_log_entry",
    queue="embeddings",
    max_retries=3,
    acks_late=True,
    default_retry_delay=30,
)
def embed_log_entry(self: Any, log_id_str: str) -> None:
    """Generate and store the embedding for a log entry.

    Steps:
      1. Load the log entry from DB.
      2. Decrypt content.
      3. Generate 384-dim embedding via Qdrant inference.
      4. Upsert vector to Qdrant.
      5. Set embedding_status='embedded'.

    On failure: retries up to 3 times with exponential backoff.
    Sets embedding_status='failed' after all retries are exhausted.
    """
    log_id = uuid.UUID(log_id_str)
    logger.info("embed_log_entry_start", log_id=log_id_str)

    try:
        # ── Load entry ──────────────────────────────────────────────────
        entry = asyncio.run(_load_log_entry(log_id))
        if entry is None:
            logger.warning("embed_log_entry_skipped", log_id=log_id_str, reason="not found")
            return

        # ── Generate embedding ──────────────────────────────────────────
        plaintext = decrypt_content(entry.content_encrypted)
        vector = generate_embedding(plaintext)

        # ── Upsert to Qdrant ────────────────────────────────────────────
        asyncio.run(
            upsert_log_vector(
                log_id=entry.id,
                user_id=entry.user_id,
                context_id=entry.context_id,
                vector=vector,
                date_start=entry.date_start.isoformat(),
                date_end=entry.date_end.isoformat(),
            )
        )

        # ── Mark embedded ────────────────────────────────────────────────
        asyncio.run(_set_embedding_status(log_id, "embedded"))
        logger.info("embed_log_entry_success", log_id=log_id_str)

    except Exception as exc:
        logger.error(
            "embed_log_entry_failed",
            log_id=log_id_str,
            error=str(exc),
            attempt=self.request.retries + 1,
        )
        try:
            raise self.retry(
                exc=exc,
                countdown=30 * (2 ** self.request.retries),
            )
        except self.MaxRetriesExceededError:
            # Exhausted retries — mark as failed so the UI can surface this
            asyncio.run(_set_embedding_status(log_id, "failed"))
            logger.error("embed_log_entry_max_retries", log_id=log_id_str)


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="app.workers.embedding_tasks.delete_log_embedding",
    queue="embeddings",
    max_retries=3,
    acks_late=True,
    default_retry_delay=30,
)
def delete_log_embedding(self: Any, log_id_str: str) -> None:
    """Remove the Qdrant vector for a soft-deleted log entry.

    Idempotent — no error if the vector doesn't exist.
    Retries up to 3 times on network failure.
    """
    log_id = uuid.UUID(log_id_str)
    logger.info("delete_log_embedding_start", log_id=log_id_str)

    try:
        asyncio.run(delete_log_vector(log_id))
        logger.info("delete_log_embedding_success", log_id=log_id_str)
    except Exception as exc:
        logger.error(
            "delete_log_embedding_failed",
            log_id=log_id_str,
            error=str(exc),
            attempt=self.request.retries + 1,
        )
        raise self.retry(
            exc=exc,
            countdown=30 * (2 ** self.request.retries),
        ) from exc
