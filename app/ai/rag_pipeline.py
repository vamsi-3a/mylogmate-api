"""RAG pipeline — retrieval-augmented generation for work-log recall.

Flow:
  1. Generate query embedding (Qdrant Cloud inference).
  2. Retrieve top-k similar log vectors filtered by user_id (+ optional context_id).
  3. Fetch the actual decrypted log content from PostgreSQL for each hit.
  4. Build a context block from the retrieved logs.
  5. Call the LLM (Groq / Ollama) with system + user messages.
  6. Return the AI answer and the source log IDs used as context.

Rules (ai-module.md):
  - NEVER call Groq/Ollama directly — always go through get_llm_provider().
  - All prompts come from app/ai/prompts.py.
  - Qdrant search MUST filter by user_id (enforced inside search_log_vectors).
  - NEVER log user queries in full — only a 150-char preview.
"""

from __future__ import annotations

import time
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import generate_embedding
from app.ai.llm_provider import get_llm_provider
from app.ai.prompts import build_context_block, build_recall_messages
from app.ai.qdrant_store import search_log_vectors
from app.core.security import decrypt_content
from app.db.models.log_entry import LogEntry

logger = structlog.get_logger()

# How many vector search results to retrieve
_TOP_K = 8


async def run_recall_query(
    db: AsyncSession,
    user_id: uuid.UUID,
    context_id: uuid.UUID,
    query: str,
) -> tuple[str, list[uuid.UUID], int]:
    """Run a RAG recall query and return the LLM answer.

    Args:
        db: Async DB session for loading log content.
        user_id: The authenticated user's ID (security boundary).
        context_id: The context to restrict the search to.
        query: The user's natural-language question.

    Returns:
        Tuple of (answer_text, source_log_ids, latency_ms).
        source_log_ids: UUIDs of the logs used as context.
        latency_ms: End-to-end wall time in milliseconds.

    Raises:
        RuntimeError: If embedding generation or LLM call fails.
    """
    t_start = time.perf_counter()

    # NEVER log the full query — only a preview
    query_preview = query[:150]
    logger.info("rag_query_start", user_id=str(user_id), query_preview=query_preview)

    # ── 1. Embed the query ────────────────────────────────────────────────
    query_vector = generate_embedding(query)

    # ── 2. Retrieve similar vectors (always filtered by user_id) ─────────
    hits = await search_log_vectors(
        user_id=user_id,
        query_vector=query_vector,
        limit=_TOP_K,
        context_id=context_id,
    )

    # ── 3. Load + decrypt log content from DB ─────────────────────────────
    source_ids: list[uuid.UUID] = []
    enriched_hits: list[dict[str, object]] = []

    if hits:
        log_ids = [uuid.UUID(str(h["log_id"])) for h in hits]

        result = await db.execute(
            select(LogEntry).where(
                LogEntry.id.in_(log_ids),
                LogEntry.user_id == user_id,  # re-verify ownership
                LogEntry.is_deleted.is_(False),
            )
        )
        log_map: dict[uuid.UUID, LogEntry] = {
            e.id: e for e in result.scalars().all()
        }

        for hit in hits:
            log_id = uuid.UUID(str(hit["log_id"]))
            entry = log_map.get(log_id)
            if entry is None:
                continue  # vector references deleted/missing log — skip
            source_ids.append(log_id)
            enriched_hits.append(
                {
                    "log_id": str(log_id),
                    "date_start": str(hit.get("date_start", "")),
                    "content": decrypt_content(entry.content_encrypted),
                }
            )

    logger.info("rag_hits_retrieved", hit_count=len(enriched_hits))

    # ── 4. Build prompt ───────────────────────────────────────────────────
    context_block = build_context_block(enriched_hits)
    messages = build_recall_messages(user_query=query, context_block=context_block)

    # ── 5. Call LLM ───────────────────────────────────────────────────────
    llm = get_llm_provider()
    answer = await llm.acomplete(messages)

    latency_ms = round((time.perf_counter() - t_start) * 1000)
    logger.info(
        "rag_query_complete",
        user_id=str(user_id),
        latency_ms=latency_ms,
        source_count=len(source_ids),
    )

    return answer, source_ids, latency_ms
