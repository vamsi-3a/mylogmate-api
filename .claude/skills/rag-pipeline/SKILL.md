---
name: rag-pipeline
description: Use when working on the RAG pipeline, embedding generation, vector search, LLM queries, or any AI-related code in app/ai/. Trigger on any file in app/ai/ or recall-related endpoints.
---

# RAG Pipeline

## Flow
```
Log Created → Celery → Decrypt → Embed (all-MiniLM-L6-v2) → Store in Qdrant
User Query → Embed Query → Qdrant Search (filtered) → Decrypt Retrieved → LLM (Groq) → Response
```

## Embedding (app/ai/embeddings.py)
```python
from sentence_transformers import SentenceTransformer
_model: SentenceTransformer | None = None

def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model

def generate_embedding(text: str) -> list[float]:
    return get_embedding_model().encode(text).tolist()
```
- 384-dim vectors. Cosine similarity. Load model once, reuse.

## LLM Abstraction (app/ai/llm_provider.py)
```python
class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, system_prompt: str, user_prompt: str, context: str) -> str: ...

class GroqProvider(LLMProvider):
    async def generate(self, system_prompt: str, user_prompt: str, context: str) -> str: ...

class OllamaProvider(LLMProvider):
    async def generate(self, system_prompt: str, user_prompt: str, context: str) -> str: ...

def get_llm_provider() -> LLMProvider:
    provider_map = {"groq": GroqProvider, "ollama": OllamaProvider}
    return provider_map[settings.LLM_PROVIDER]()
```
Switch with LLM_PROVIDER env var. Nothing else changes.

## Prompts (app/ai/prompts.py)
```python
RECALL_SYSTEM_PROMPT = """You are a helpful assistant that answers questions about a user's work logs.
Answer ONLY based on the provided log entries. If insufficient information, say so clearly.
Do NOT hallucinate. Be concise and structured."""
```
ALL prompts centralized here. Never inline prompt strings.

## Rate Limiting
50 AI queries/user/day. Check ai_query_logs count before each query. Return 429 when exceeded.
