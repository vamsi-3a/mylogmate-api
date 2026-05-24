---
name: qdrant-vectors
description: Use when working with Qdrant vector database operations — storing embeddings, searching vectors, managing collections, or filtering. Trigger on app/ai/vector_store.py or any Qdrant-related code.
---

# Qdrant Vector Patterns

## Collection Config
- Name: `log_entries`
- Vector size: 384 (all-MiniLM-L6-v2)
- Distance: Cosine

## Payload Fields
- user_id (keyword) — MANDATORY filter
- context_id (keyword)
- log_entry_id (keyword) — for point ID and delete operations
- date_start (integer, epoch days)
- date_end (integer, epoch days)
- tag_ids (keyword array)

## Operations
```python
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue, Range, MatchAny

async def upsert(log_entry_id: str, vector: list[float], metadata: dict):
    client.upsert(collection_name="log_entries",
        points=[PointStruct(id=log_entry_id, vector=vector, payload=metadata)])

async def delete(log_entry_id: str):
    client.delete(collection_name="log_entries",
        points_selector=PointIdsList(points=[log_entry_id]))

async def search(query_vector: list[float], user_id: str, context_id: str,
                 date_start: int, date_end: int, include_tags: list[str] | None = None,
                 exclude_tags: list[str] | None = None, top_k: int = 10):
    must = [
        FieldCondition(key="user_id", match=MatchValue(value=user_id)),
        FieldCondition(key="context_id", match=MatchValue(value=context_id)),
        FieldCondition(key="date_start", range=Range(gte=date_start)),
        FieldCondition(key="date_end", range=Range(lte=date_end)),
    ]
    if include_tags:
        must.append(FieldCondition(key="tag_ids", match=MatchAny(any=include_tags)))
    must_not = []
    if exclude_tags:
        must_not.append(FieldCondition(key="tag_ids", match=MatchAny(any=exclude_tags)))
    return client.search(collection_name="log_entries", query_vector=query_vector,
        query_filter=Filter(must=must, must_not=must_not), limit=top_k)
```

## Rules
- ALWAYS filter by user_id. No exceptions. Security requirement.
- Use epoch days (not seconds) for date fields to keep integer range manageable
- Use context7 MCP to check current qdrant-client Python API before writing code
- Point ID = log_entry_id (string UUID)
