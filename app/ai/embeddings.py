"""Embedding generation — synchronous interface for Celery tasks.

Uses fastembed (ONNX runtime, no PyTorch) with the `BAAI/bge-small-en-v1.5`
model — 384 dimensions, same as the all-MiniLM family but with better quality.

The model file is downloaded on first use and cached under /tmp/fastembed_cache.
In Docker we pre-download it at build time so cold starts are fast.

Raises RuntimeError on any failure — caller (Celery task) handles retry logic.

Note: This module provides a SYNC interface (not async) because Celery tasks
run in a standard prefork worker without an event loop.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from fastembed import TextEmbedding

logger = structlog.get_logger()

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"  # 384-dim, ONNX, ~130MB
EMBEDDING_DIM = 384

# Lazy singleton — model loads on first call, reused for life of process.
# Lock prevents two threads from loading concurrently (worker prefork = 1 proc).
_model: TextEmbedding | None = None
_model_lock = threading.Lock()


def _get_model() -> TextEmbedding:
    """Return the singleton TextEmbedding instance, loading on first call."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:  # double-checked locking
                from fastembed import TextEmbedding

                logger.info("embedding_model_loading", model=EMBEDDING_MODEL)
                _model = TextEmbedding(model_name=EMBEDDING_MODEL)
                logger.info("embedding_model_loaded", model=EMBEDDING_MODEL)
    return _model


def generate_embedding(text: str) -> list[float]:
    """Generate a 384-dim embedding for the given text.

    Strips and truncates text to a safe bound before tokenization.
    Raises ValueError on empty input.
    Raises RuntimeError on model failure — Celery task retries on this.
    """
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text")

    truncated = text.strip()[:8_192]

    try:
        model = _get_model()
        # fastembed returns a generator yielding numpy arrays
        vectors = list(model.embed([truncated]))
    except Exception as exc:
        raise RuntimeError(f"Embedding generation failed: {exc}") from exc

    if not vectors:
        raise RuntimeError("Embedding model returned no vectors")

    vector = vectors[0].tolist()
    if len(vector) != EMBEDDING_DIM:
        raise RuntimeError(
            f"Expected {EMBEDDING_DIM}-dim vector, got {len(vector)}"
        )

    logger.debug("embedding_generated", dims=len(vector))
    return vector
