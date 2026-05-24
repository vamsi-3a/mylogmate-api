"""Qdrant vector store unit tests.

All Qdrant client calls are mocked — no real Qdrant instance required.

Coverage:
- get_qdrant_client()       — singleton creation and reuse
- ensure_collection()       — creates collection + indices when missing,
                              skips when already present
- upsert_log_vector()       — correct PointStruct payload
- delete_log_vector()       — passes log_id as string to delete()
- search_log_vectors()      — mandatory user_id filter enforced,
                              optional context_id filter applied,
                              result mapping correct
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Helpers ───────────────────────────────────────────────────────────────


def _mock_collection(name: str) -> MagicMock:
    c = MagicMock()
    c.name = name
    return c


def _make_search_hit(log_id: str, user_id: str, score: float = 0.95) -> MagicMock:
    hit = MagicMock()
    hit.score = score
    hit.payload = {
        "log_id": log_id,
        "user_id": user_id,
        "context_id": str(uuid.uuid4()),
        "date_start": "2026-05-01",
        "date_end": "2026-05-01",
    }
    return hit


def _query_response(*hits: MagicMock) -> MagicMock:
    """Wrap hits in a mock matching QueryResponse (has .points attribute)."""
    resp = MagicMock()
    resp.points = list(hits)
    return resp


# ── get_qdrant_client ─────────────────────────────────────────────────────


def test_get_qdrant_client_singleton() -> None:
    """Returns the same AsyncQdrantClient instance on repeated calls."""
    import app.ai.qdrant_store as qs

    # Reset singleton for clean test
    qs._client = None  # noqa: SLF001

    with patch("app.ai.qdrant_store.AsyncQdrantClient") as mock_client_cls:
        instance = MagicMock()
        mock_client_cls.return_value = instance

        c1 = qs.get_qdrant_client()
        c2 = qs.get_qdrant_client()

        assert c1 is c2
        assert mock_client_cls.call_count == 1  # only constructed once

    qs._client = None  # cleanup


# ── ensure_collection ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ensure_collection_creates_when_missing() -> None:
    """Creates the collection and payload indices when not present."""
    import app.ai.qdrant_store as qs

    qs._client = None  # noqa: SLF001
    mock_client = AsyncMock()
    collections_resp = MagicMock()
    collections_resp.collections = []  # no collections
    mock_client.get_collections.return_value = collections_resp
    mock_client.create_collection = AsyncMock()
    mock_client.create_payload_index = AsyncMock()

    with patch("app.ai.qdrant_store.get_qdrant_client", return_value=mock_client):
        await qs.ensure_collection()

    mock_client.create_collection.assert_called_once()
    assert mock_client.create_payload_index.call_count == 2  # user_id + context_id


@pytest.mark.asyncio
async def test_ensure_collection_skips_when_exists() -> None:
    """Does not recreate collection if it already exists."""
    import app.ai.qdrant_store as qs

    qs._client = None  # noqa: SLF001
    mock_client = AsyncMock()
    collections_resp = MagicMock()
    collections_resp.collections = [_mock_collection(qs._COLLECTION)]  # noqa: SLF001
    mock_client.get_collections.return_value = collections_resp
    mock_client.create_collection = AsyncMock()

    with patch("app.ai.qdrant_store.get_qdrant_client", return_value=mock_client):
        await qs.ensure_collection()

    mock_client.create_collection.assert_not_called()


# ── upsert_log_vector ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_log_vector_payload() -> None:
    """Upserts a PointStruct with correct id, vector, and payload."""
    import app.ai.qdrant_store as qs

    log_id = uuid.uuid4()
    user_id = uuid.uuid4()
    context_id = uuid.uuid4()
    vector = [0.1] * qs.EMBEDDING_DIM

    mock_client = AsyncMock()
    mock_client.upsert = AsyncMock()

    with patch("app.ai.qdrant_store.get_qdrant_client", return_value=mock_client):
        await qs.upsert_log_vector(
            log_id=log_id,
            user_id=user_id,
            context_id=context_id,
            vector=vector,
            date_start="2026-05-01",
            date_end="2026-05-01",
        )

    mock_client.upsert.assert_called_once()
    call_kwargs = mock_client.upsert.call_args.kwargs
    point = call_kwargs["points"][0]

    assert point.id == str(log_id)
    assert point.vector == vector
    assert point.payload["user_id"] == str(user_id)
    assert point.payload["context_id"] == str(context_id)
    assert point.payload["log_id"] == str(log_id)
    assert point.payload["date_start"] == "2026-05-01"


# ── delete_log_vector ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_log_vector() -> None:
    """Calls client.delete with the log_id as string."""
    import app.ai.qdrant_store as qs

    log_id = uuid.uuid4()
    mock_client = AsyncMock()
    mock_client.delete = AsyncMock()

    with patch("app.ai.qdrant_store.get_qdrant_client", return_value=mock_client):
        await qs.delete_log_vector(log_id)

    mock_client.delete.assert_called_once()
    call_kwargs = mock_client.delete.call_args.kwargs
    assert str(log_id) in call_kwargs["points_selector"]


# ── search_log_vectors ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_user_id_filter_always_applied() -> None:
    """user_id filter is always present in the search query."""
    import app.ai.qdrant_store as qs

    user_id = uuid.uuid4()
    vector = [0.1] * qs.EMBEDDING_DIM
    hit = _make_search_hit(str(uuid.uuid4()), str(user_id))

    mock_client = AsyncMock()
    mock_client.query_points = AsyncMock(return_value=_query_response(hit))

    with patch("app.ai.qdrant_store.get_qdrant_client", return_value=mock_client):
        await qs.search_log_vectors(user_id=user_id, query_vector=vector, limit=5)

    mock_client.query_points.assert_called_once()
    search_kwargs = mock_client.query_points.call_args.kwargs
    query_filter = search_kwargs["query_filter"]

    # Verify user_id filter is present
    conditions = query_filter.must
    user_cond = next(c for c in conditions if c.key == "user_id")
    assert user_cond.match.value == str(user_id)

    # context_id filter should NOT be present (not passed)
    assert not any(c.key == "context_id" for c in conditions)


@pytest.mark.asyncio
async def test_search_context_id_filter_optional() -> None:
    """context_id filter is appended when provided."""
    import app.ai.qdrant_store as qs

    user_id = uuid.uuid4()
    context_id = uuid.uuid4()
    vector = [0.1] * qs.EMBEDDING_DIM

    mock_client = AsyncMock()
    mock_client.query_points = AsyncMock(return_value=_query_response())

    with patch("app.ai.qdrant_store.get_qdrant_client", return_value=mock_client):
        await qs.search_log_vectors(
            user_id=user_id,
            query_vector=vector,
            context_id=context_id,
        )

    search_kwargs = mock_client.query_points.call_args.kwargs
    conditions = search_kwargs["query_filter"].must
    ctx_cond = next(c for c in conditions if c.key == "context_id")
    assert ctx_cond.match.value == str(context_id)


@pytest.mark.asyncio
async def test_search_result_mapping() -> None:
    """Results are mapped to dicts with log_id, score, etc."""
    import app.ai.qdrant_store as qs

    user_id = uuid.uuid4()
    log_id = uuid.uuid4()
    vector = [0.1] * qs.EMBEDDING_DIM
    hit = _make_search_hit(str(log_id), str(user_id), score=0.88)

    mock_client = AsyncMock()
    mock_client.query_points = AsyncMock(return_value=_query_response(hit))

    with patch("app.ai.qdrant_store.get_qdrant_client", return_value=mock_client):
        results = await qs.search_log_vectors(
            user_id=user_id, query_vector=vector
        )

    assert len(results) == 1
    assert results[0]["log_id"] == str(log_id)
    assert results[0]["user_id"] == str(user_id)
    assert results[0]["score"] == 0.88


@pytest.mark.asyncio
async def test_search_respects_limit() -> None:
    """Passes the limit parameter to the client search call."""
    import app.ai.qdrant_store as qs

    user_id = uuid.uuid4()
    vector = [0.1] * qs.EMBEDDING_DIM

    mock_client = AsyncMock()
    mock_client.query_points = AsyncMock(return_value=_query_response())

    with patch("app.ai.qdrant_store.get_qdrant_client", return_value=mock_client):
        await qs.search_log_vectors(user_id=user_id, query_vector=vector, limit=3)

    assert mock_client.query_points.call_args.kwargs["limit"] == 3
