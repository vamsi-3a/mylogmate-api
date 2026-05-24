"""Qdrant vector store — async client, collection lifecycle, and CRUD operations.

Security invariant (non-negotiable):
  Every search() call MUST include a `user_id` filter. Without it, users can
  see each other's vectors. This is enforced at the method level — there is no
  public search that skips the filter.

Collection schema
  name:       settings.QDRANT_COLLECTION  (default: "log_entries")
  vector_dim: EMBEDDING_DIM = 384         (all-MiniLM-L6-v2)
  distance:   Cosine

Payload fields (searchable / filterable)
  user_id    : str  — UUID of the owning user (ALWAYS filtered)
  context_id : str  — UUID of the context (optional filter)
  log_id     : str  — UUID of the log entry (same as point ID, for clarity)
  date_start : str  — ISO date string "YYYY-MM-DD"
  date_end   : str  — ISO date string "YYYY-MM-DD"
"""

from __future__ import annotations

import uuid

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    HnswConfigDiff,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from app.core.config import settings

logger = structlog.get_logger()

# ── Constants ─────────────────────────────────────────────────────────────

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output dimension
_COLLECTION = settings.QDRANT_COLLECTION

# ── Singleton client ──────────────────────────────────────────────────────

_client: AsyncQdrantClient | None = None


def get_qdrant_client() -> AsyncQdrantClient:
    """Return the shared AsyncQdrantClient instance (lazy init).

    Call this from service/worker code — never construct a new client directly.
    """
    global _client  # noqa: PLW0603
    if _client is None:
        _client = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY or None,
            timeout=10,
        )
    return _client


async def close_qdrant_client() -> None:
    """Close and discard the singleton client (called on app shutdown)."""
    global _client  # noqa: PLW0603
    if _client is not None:
        await _client.close()
        _client = None
        logger.info("qdrant_client_closed")


# ── Collection lifecycle ──────────────────────────────────────────────────


async def ensure_collection() -> None:
    """Create the log_entries collection if it does not already exist.

    Idempotent — safe to call on every startup. Also creates payload indices
    on `user_id` and `context_id` to make filtering efficient.
    """
    client = get_qdrant_client()
    response = await client.get_collections()
    existing = {c.name for c in response.collections}

    if _COLLECTION not in existing:
        await client.create_collection(
            collection_name=_COLLECTION,
            vectors_config=VectorParams(
                size=EMBEDDING_DIM,
                distance=Distance.COSINE,
            ),
            hnsw_config=HnswConfigDiff(
                m=16,
                ef_construct=100,
            ),
        )
        logger.info("qdrant_collection_created", collection=_COLLECTION)

        # ── Payload indices for fast filtering ────────────────────────────
        await client.create_payload_index(
            collection_name=_COLLECTION,
            field_name="user_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        await client.create_payload_index(
            collection_name=_COLLECTION,
            field_name="context_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        logger.info("qdrant_payload_indices_created", collection=_COLLECTION)
    else:
        logger.info("qdrant_collection_exists", collection=_COLLECTION)


# ── Vector CRUD ───────────────────────────────────────────────────────────


async def upsert_log_vector(
    log_id: uuid.UUID,
    user_id: uuid.UUID,
    context_id: uuid.UUID,
    vector: list[float],
    date_start: str,
    date_end: str,
) -> None:
    """Insert or replace the embedding vector for a log entry.

    The point ID is the log_id UUID (stored as string for Qdrant compatibility).
    Payload includes all fields needed for retrieval and filtering.
    """
    client = get_qdrant_client()
    point = PointStruct(
        id=str(log_id),
        vector=vector,
        payload={
            "log_id": str(log_id),
            "user_id": str(user_id),
            "context_id": str(context_id),
            "date_start": date_start,
            "date_end": date_end,
        },
    )
    await client.upsert(
        collection_name=_COLLECTION,
        points=[point],
        wait=True,
    )
    logger.info("qdrant_upsert", log_id=str(log_id))


async def delete_log_vector(log_id: uuid.UUID) -> None:
    """Remove the embedding vector for a soft-deleted log entry.

    Called from the Celery delete_log_embedding task (Step 12).
    Idempotent — no error if the point doesn't exist.
    """
    client = get_qdrant_client()
    await client.delete(
        collection_name=_COLLECTION,
        points_selector=[str(log_id)],
        wait=True,
    )
    logger.info("qdrant_delete", log_id=str(log_id))


async def search_log_vectors(
    user_id: uuid.UUID,
    query_vector: list[float],
    limit: int = 10,
    context_id: uuid.UUID | None = None,
) -> list[dict[str, object]]:
    """Semantic search over the user's log entries.

    Security: user_id filter is ALWAYS applied — there is no code path
    that searches across all users.

    Returns a list of payload dicts (+ score) for the top-k matches.
    """
    # ── Mandatory user_id filter ──────────────────────────────────────────
    must_conditions = [
        FieldCondition(key="user_id", match=MatchValue(value=str(user_id)))
    ]

    # ── Optional context_id filter ────────────────────────────────────────
    if context_id is not None:
        must_conditions.append(
            FieldCondition(key="context_id", match=MatchValue(value=str(context_id)))
        )

    search_filter = Filter(must=must_conditions)

    # query_points() replaces the deprecated search() in qdrant-client >= 1.7
    response = await get_qdrant_client().query_points(
        collection_name=_COLLECTION,
        query=query_vector,
        query_filter=search_filter,
        limit=limit,
        with_payload=True,
    )

    return [
        {
            "log_id": hit.payload.get("log_id") if hit.payload else None,
            "user_id": hit.payload.get("user_id") if hit.payload else None,
            "context_id": hit.payload.get("context_id") if hit.payload else None,
            "date_start": hit.payload.get("date_start") if hit.payload else None,
            "date_end": hit.payload.get("date_end") if hit.payload else None,
            "score": hit.score,
        }
        for hit in response.points
    ]
