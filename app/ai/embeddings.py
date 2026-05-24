"""Embedding generation — synchronous interface for Celery tasks.

Uses Qdrant Cloud's OpenAI-compatible inference endpoint to generate embeddings
server-side. No local model required.

Endpoint: POST {QDRANT_URL}/v1/embeddings
Model:    Qdrant/all-MiniLM-L6-v2 (384 dimensions, cosine distance)

Raises RuntimeError on any failure — caller (Celery task) handles retry logic.

Note: This module provides a SYNC interface (not async) because Celery tasks
run in a standard prefork worker without an event loop.
"""

from __future__ import annotations

import requests
import structlog

from app.core.config import settings

logger = structlog.get_logger()

EMBEDDING_MODEL = "Qdrant/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
_TIMEOUT_SECONDS = 15


def generate_embedding(text: str) -> list[float]:
    """Generate a 384-dim embedding for the given text via Qdrant Cloud inference.

    Strips and truncates text to 512 characters (model context limit).
    Raises RuntimeError if the API call fails — Celery task retries on this.
    """
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text")

    # Truncate to model's effective context window
    truncated = text.strip()[:8_192]  # safe upper bound before tokenization

    url = f"{settings.QDRANT_URL.rstrip('/')}/v1/embeddings"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.QDRANT_API_KEY:
        headers["api-key"] = settings.QDRANT_API_KEY

    try:
        resp = requests.post(
            url,
            json={"model": EMBEDDING_MODEL, "input": [truncated]},
            headers=headers,
            timeout=_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Qdrant inference request failed: {exc}") from exc

    try:
        data = resp.json()
        vector: list[float] = data["data"][0]["embedding"]
    except (KeyError, IndexError, ValueError) as exc:
        raise RuntimeError(f"Unexpected Qdrant inference response: {exc}") from exc

    if len(vector) != EMBEDDING_DIM:
        raise RuntimeError(
            f"Expected {EMBEDDING_DIM}-dim vector, got {len(vector)}"
        )

    logger.debug("embedding_generated", dims=len(vector))
    return vector
