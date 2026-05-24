# MyLogMate API

## Project
Work-logging + AI-recall backend. Python FastAPI. Users log work, tag it, query with AI for reviews.

## Stack
Python 3.12 | FastAPI | SQLAlchemy 2.0 async | Alembic | PostgreSQL 16 (Neon) | Qdrant Cloud | Celery + Redis Cloud | LlamaIndex | sentence-transformers | Groq API | Pydantic v2 | JWT + Google OAuth | bcrypt | structlog

## Commands
```
docker-compose up          # all services locally
make test                  # pytest -v
make lint                  # ruff check + mypy
make migrate               # alembic upgrade head
make migration msg="..."   # alembic revision --autogenerate
make seed                  # sample templates + admin user
make format                # ruff format .
```

## Architecture
- Routes (app/api/v1/) → thin: validate → call service → return ApiResponse
- Services (app/services/) → all business logic
- Models (app/db/models/) → data-only SQLAlchemy
- Schemas (app/schemas/) → Pydantic request/response
- AI module (app/ai/) → fully isolated RAG pipeline
- Workers (app/workers/) → Celery async tasks
- One file per model, service, router, schema

## Conventions
- Type hints on ALL function signatures (params + return)
- async def for all route handlers and service methods
- snake_case files/functions/vars. PascalCase classes.
- 88 char line limit. f-strings only. Imports sorted by ruff.
- All endpoints: /api/v1/ prefix
- Response: {"data": ..., "message": "...", "success": bool}
- UUIDs for all PKs. TIMESTAMPTZ UTC. Alembic for all migrations.
- Log content AES-256 encrypted. NEVER plain text in DB.
- Every DB query filters by user_id. Data isolation is non-negotiable.
- Conventional Commits: feat:, fix:, chore:, refactor:, test:, docs:
- Separate commits per logical change. Never .env or secrets in code.

## MCP
- Use context7 for current library docs (FastAPI, SQLAlchemy, LlamaIndex, Qdrant, Celery, Pydantic)
- Always fetch docs before generating code that depends on specific API signatures

## Forbidden
- NEVER store plain text log content in DB
- NEVER hardcode secrets/URLs/keys
- NEVER skip Pydantic validation
- NEVER expose sequential IDs
- NEVER write business logic in routes
- NEVER call external APIs synchronously in route handlers for heavy tasks
- NEVER commit without running make lint first
