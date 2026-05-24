"""Celery embedding tasks — async embedding lifecycle for log entries.

Task lifecycle:
  embed_log_entry       — triggered after create or update
  delete_log_embedding  — triggered after soft-delete

Rules (workers.md):
  - bind=True, max_retries=3, acks_late=True
  - Exponential backoff: countdown=30 * (2 ** retry_count)
  - Use asyncio.run() to call async DB/Qdrant code from the sync Celery context
  - Log start, success, and failure with structlog

Event-loop discipline:
  Celery tasks are sync. We use asyncio.run() ONCE per task to host all the
  async work — never twice. The DB engine and Qdrant client both hold state
  bound to whichever event loop created their first connection; a second
  asyncio.run() in the same task would get a fresh loop and crash with
  "Event loop is closed" when trying to reuse those connections.

  After each task we close the Qdrant singleton so the next task starts
  clean on a fresh loop. The async DB engine is recycled by pool_pre_ping.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import structlog
from sqlalchemy import select

from app.ai.embeddings import generate_embedding
from app.ai.qdrant_store import (
    close_qdrant_client,
    delete_log_vector,
    upsert_log_vector,
)
from app.core.security import decrypt_content
from app.db.models.log_entry import LogEntry
from app.db.session import AsyncSessionLocal, engine
from app.workers.celery_app import celery_app

logger = structlog.get_logger()


# ── Async pipeline (single coroutine per task) ────────────────────────────


async def _embed_pipeline(log_id: uuid.UUID) -> str:
    """Full embed lifecycle: load → decrypt → embed → upsert → mark.

    Returns the final embedding_status ("embedded" or "skipped").
    """
    try:
        # ── Load entry ──────────────────────────────────────────────────
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(LogEntry).where(
                    LogEntry.id == log_id,
                    LogEntry.is_deleted.is_(False),
                )
            )
            entry = result.scalar_one_or_none()
            if entry is None:
                return "skipped"

            content_encrypted = entry.content_encrypted
            user_id = entry.user_id
            context_id = entry.context_id
            date_start_iso = entry.date_start.isoformat()
            date_end_iso = entry.date_end.isoformat()

        # ── Decrypt + embed (CPU-bound, but cheap enough to do inline) ──
        plaintext = decrypt_content(content_encrypted)
        vector = generate_embedding(plaintext)

        # ── Upsert to Qdrant ────────────────────────────────────────────
        await upsert_log_vector(
            log_id=log_id,
            user_id=user_id,
            context_id=context_id,
            vector=vector,
            date_start=date_start_iso,
            date_end=date_end_iso,
        )

        # ── Mark embedded ───────────────────────────────────────────────
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(LogEntry).where(LogEntry.id == log_id)
            )
            mark_entry = result.scalar_one_or_none()
            if mark_entry is not None:
                mark_entry.embedding_status = "embedded"
                await session.commit()

        return "embedded"
    finally:
        # Reset per-loop singletons so the next Celery task starts clean.
        await close_qdrant_client()
        await engine.dispose()


async def _set_status_async(log_id: uuid.UUID, status: str) -> None:
    """Standalone async helper for marking a log as 'failed' from the error
    handler. Runs in its own asyncio.run() so the main pipeline can have
    already cleaned up its loop.
    """
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(LogEntry).where(LogEntry.id == log_id)
            )
            entry = result.scalar_one_or_none()
            if entry is not None:
                entry.embedding_status = status
                await session.commit()
    finally:
        await engine.dispose()


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

    On failure: retries up to 3 times with exponential backoff.
    Sets embedding_status='failed' after all retries are exhausted.
    """
    log_id = uuid.UUID(log_id_str)
    logger.info("embed_log_entry_start", log_id=log_id_str)

    try:
        status = asyncio.run(_embed_pipeline(log_id))
        logger.info("embed_log_entry_success", log_id=log_id_str, status=status)
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
            asyncio.run(_set_status_async(log_id, "failed"))
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

    async def _delete() -> None:
        try:
            await delete_log_vector(log_id)
        finally:
            await close_qdrant_client()

    try:
        asyncio.run(_delete())
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
