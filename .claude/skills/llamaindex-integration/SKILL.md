---
name: llamaindex-integration
description: Use when setting up LlamaIndex RAG pipeline, query engine, vector store index, or LLM integration. Trigger on app/ai/rag_engine.py or when orchestrating the retrieval-generation flow. ALWAYS use context7 MCP to fetch current LlamaIndex docs first — the API changes frequently.
---

# LlamaIndex Integration

## IMPORTANT
LlamaIndex API changes frequently between versions. ALWAYS use context7 MCP to fetch current documentation before writing any LlamaIndex code:
```
Use context7 to fetch LlamaIndex documentation for QdrantVectorStore and query engine setup
```

## High-Level Pattern (app/ai/rag_engine.py)
```python
# Conceptual — verify exact API with context7 before implementing
from llama_index.core import VectorStoreIndex, Settings
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.llms.groq import Groq

# Configure LlamaIndex to use Groq
Settings.llm = Groq(model="llama-3.1-8b-instant", api_key=settings.GROQ_API_KEY)

# Create vector store backed by Qdrant
vector_store = QdrantVectorStore(client=qdrant_client, collection_name="log_entries")
index = VectorStoreIndex.from_vector_store(vector_store)

# Query with pre-filtered retrieval
query_engine = index.as_query_engine(similarity_top_k=10)
response = query_engine.query("What were my key achievements?")
```

## Rules
- Fetch current LlamaIndex docs via context7 before EVERY implementation
- Pin LlamaIndex version in pyproject.toml
- The system prompt (from app/ai/prompts.py) instructs anti-hallucination
- Retrieval is pre-filtered by user_id + context_id + date range via Qdrant
- Response is returned to the user and stored in chat_messages
