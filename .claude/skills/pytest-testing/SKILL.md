---
name: pytest-testing
description: Use when writing tests — unit tests for services/models, API integration tests for endpoints, or mocking external services. Trigger on any file in tests/ or when creating new features that need test coverage.
---

# Testing Patterns

## Test File Naming
```
tests/
├── conftest.py                # Shared fixtures
├── api/v1/test_auth.py        # Mirrors app/api/v1/auth.py
├── api/v1/test_logs.py
├── services/test_log_service.py
├── ai/test_embeddings.py
└── e2e/test_log_recall_flow.py
```

## Essential Fixtures (conftest.py)
```python
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app
from app.db.base import Base

TEST_DB_URL = "postgresql+asyncpg://test:test@localhost:5432/mylogmate_test"

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession)
    async with session_factory() as session:
        yield session
        await session.rollback()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
async def auth_headers(client):
    await client.post("/api/v1/auth/signup", json={
        "username": "testuser", "email": "test@test.com", "password": "SecurePass123!"
    })
    resp = await client.post("/api/v1/auth/login", json={"username": "testuser", "password": "SecurePass123!"})
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def mock_celery(mocker):
    mocker.patch("app.workers.embedding_tasks.generate_and_store_embedding.delay")
    mocker.patch("app.workers.embedding_tasks.delete_embedding.delay")
    mocker.patch("app.workers.email_tasks.send_password_reset_email.delay")
```

## Unit Test Pattern
```python
@pytest.mark.asyncio
async def test_create_log_entry_success(client, auth_headers, mock_celery):
    resp = await client.post("/api/v1/logs", headers=auth_headers, json={
        "context_id": "self-context-uuid", "content": "Shipped feature X",
        "date_type": "daily", "date_start": "2026-05-21", "date_end": "2026-05-21"
    })
    assert resp.status_code == 201
    assert resp.json()["success"] is True
    assert "Shipped feature X" in resp.json()["data"]["content"]
    mock_celery.assert_called_once()

@pytest.mark.asyncio
async def test_create_log_entry_unauthorized(client):
    resp = await client.post("/api/v1/logs", json={"content": "test"})
    assert resp.status_code == 401

@pytest.mark.asyncio
async def test_create_log_entry_validation_error(client, auth_headers):
    resp = await client.post("/api/v1/logs", headers=auth_headers, json={"content": ""})
    assert resp.status_code == 422
```

## E2E Test Pattern
```python
@pytest.mark.asyncio
async def test_log_and_recall_flow(client, auth_headers, mock_celery, mock_qdrant, mock_groq):
    # 1. Create a log
    log_resp = await client.post("/api/v1/logs", headers=auth_headers, json={...})
    assert log_resp.status_code == 201
    # 2. Query recall
    recall_resp = await client.post("/api/v1/recall/query", headers=auth_headers, json={
        "context_id": "...", "prompt": "Summarize my work", "time_start": "2026-05-01", "time_end": "2026-05-31"
    })
    assert recall_resp.status_code == 200
    assert recall_resp.json()["data"]["response"] is not None
```

## Coverage Rules
- Every endpoint: happy path + 401 + 422 (validation) minimum
- Services: test business logic independently from routes
- Mock ALL externals: Groq, Qdrant, SMTP, Celery
- E2E: test critical flows (signup→login→log→recall)
- Run: `pytest -v --tb=short`
