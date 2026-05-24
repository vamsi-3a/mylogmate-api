---
path: app/ai/**
---
- Use LLM provider abstraction. Never call Groq/Ollama directly outside llm_provider.py.
- All prompts in app/ai/prompts.py. No inline prompt strings.
- Qdrant queries MUST filter by user_id. Security requirement.
- Use context7 MCP for LlamaIndex docs — API changes between versions.
- Embedding model: all-MiniLM-L6-v2 (384 dim). Don't change without updating Qdrant collection.
