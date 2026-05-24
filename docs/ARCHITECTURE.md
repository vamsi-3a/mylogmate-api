# MyLogMate — Engineering Architecture

**Version:** 1.0 Final | **Date:** May 2026 | **Author:** Vamsi | **Status:** Locked — Ready for Development

---

## 1. Architecture Overview

### 1.1 System Summary

Classic three-tier architecture: React SPA frontend → Python FastAPI backend API → data layer (PostgreSQL + Qdrant + Redis). AI layer uses LlamaIndex for RAG, sentence-transformers for embeddings, Groq free API for LLM (modular adapter for Ollama swap).

### 1.2 Architecture Principles

- **Modularity:** Every major concern (auth, logging, RAG, LLM) is self-contained. Swapping an LLM or vector DB = changes in one file.
- **AI-code-gen friendly:** Clear naming, flat directories, minimal abstractions, explicit over implicit.
- **Production-grade from day one:** Docker, CI/CD, structured logging, error handling, validation, rate limiting — all in initial setup.
- **Free-tier optimized:** Every service fits within a free tier. Scaling up requires config changes, not rewrites.
- **Solo-dev pragmatic:** No premature microservices. No over-abstraction. Ship fast, iterate on real usage.

### 1.3 High-Level Flow

```
Frontend (React SPA on Vercel)
    → HTTPS →
Backend API (FastAPI on Render)
    → PostgreSQL (Neon) — relational data
    → Qdrant (Qdrant Cloud) — vector embeddings
    → Redis (Redis Cloud) — Celery broker + rate limiting
    → Groq API — LLM inference (via LlamaIndex)
    → Celery Worker (Render) — async embedding generation + emails
```

---

## 2. Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Frontend | React 18 + Vite + Tailwind CSS + TypeScript | Fast builds, utility-first styling, type safety. Industry standard. |
| Frontend Routing | React Router v6 | Standard for React SPAs. |
| Frontend State | Zustand | Minimal, lightweight. No Redux boilerplate. |
| Frontend HTTP | Axios | Interceptors for auth tokens, error handling. |
| Frontend Icons | lucide-react | Consistent, tree-shakable SVG icons. |
| Frontend Testing | Vitest + React Testing Library | Vite-native testing. RTL for component tests. |
| Backend | Python 3.12 + FastAPI | Async-native, auto OpenAPI docs, excellent typing. |
| Backend Validation | Pydantic v2 | Built into FastAPI. Type-safe, fast. |
| Database | PostgreSQL 16 (Neon free, 512MB) | Relational data with strong consistency. Serverless. |
| Database Driver | asyncpg + SQLAlchemy 2.0 async | Fastest Python Postgres driver + ORM with raw SQL escape hatch. |
| Vector Database | Qdrant (Qdrant Cloud free, 1GB) | Production-grade vector DB. Excellent Python client. |
| Task Queue | Celery + Redis | Industry-standard async task processing. |
| Message Broker | Redis (Redis Cloud free, 30MB) | Celery broker + rate limiting cache. |
| RAG Framework | LlamaIndex | Full RAG orchestration. Good Qdrant integration. |
| Embedding Model | all-MiniLM-L6-v2 (sentence-transformers) | CPU-friendly, 384-dim, free, no external dependency. |
| LLM (v1) | Groq API free tier | 30 RPM for Llama 3.1 8B. Fast inference. Modular adapter. |
| LLM (future) | Self-hosted Ollama | Swap via config change. LlamaIndex supports natively. |
| Auth | Custom JWT + Google OAuth 2.0 | Full control. bcrypt passwords. No third-party auth dependency. |
| Email | Gmail SMTP + aiosmtplib | Free. Password reset only. 500 emails/day. |
| Voice-to-Text | Web Speech API (browser-native) | Free, client-side. No backend processing. |
| API Docs | Swagger UI + ReDoc (FastAPI built-in) | Auto-generated. Zero extra effort. |
| Containers | Docker + Docker Compose | Consistent dev/prod. Local multi-service orchestration. |
| CI/CD | GitHub Actions | Free for public repos. Lint, test, build, deploy. |
| Frontend Hosting | Vercel (free) | Optimized for React SPAs. Auto-deploy. Custom domain. CDN. |
| Backend Hosting | Render (free) | Docker-based. Auto-deploy. Cold start ~30-50s accepted for v1. |
| Logging | structlog | Structured JSON logging. Production standard. |
| Monitoring | Built-in admin dashboard + health endpoints | Custom /admin route. /health and /ready endpoints. |

### 2.1 ORM Justification — SQLAlchemy 2.0

- 9+ tables with FKs, joins, relationships — raw SQL maintenance would be slower
- Alembic gives version-controlled migrations (essential for production)
- SQLAlchemy 2.0 async mode works natively with FastAPI
- Escape hatch: raw SQL when needed for complex/performance-critical queries
- AI agents generate better code with SQLAlchemy than raw asyncpg

---

## 3. Repository Structure

### 3.1 Frontend — mylogmate-web

```
mylogmate-web/
├── public/                     # Static assets (favicon, logo SVG)
├── src/
│   ├── api/                    # Axios client + endpoint functions
│   ├── assets/                 # SVGs, images
│   ├── components/             # Reusable UI (Button, Card, Input, Modal, Sidebar)
│   ├── hooks/                  # Custom hooks (useAuth, useApi, useVoiceInput)
│   ├── layouts/                # AppLayout (sidebar), AuthLayout (no sidebar)
│   ├── pages/                  # Route-level pages (Dashboard, Log, Recall)
│   ├── store/                  # Zustand stores (authStore, logStore, recallStore)
│   ├── types/                  # TypeScript interfaces
│   ├── utils/                  # Utilities (formatDate, truncateText)
│   ├── App.tsx                 # Root component with router
│   └── main.tsx                # Entry point
├── docs/                       # PRD.md, DESIGN_SYSTEM.md
├── .env.example
├── Dockerfile
├── tailwind.config.ts          # Design system tokens
├── vite.config.ts
├── tsconfig.json
└── package.json
```

**Convention:** One component per file. Filename = export name. Pages are flat. No nested feature folders.

### 3.2 Backend — mylogmate-api

```
mylogmate-api/
├── app/
│   ├── api/
│   │   ├── v1/                 # API v1 routes
│   │   │   ├── auth.py         # signup, login, google-oauth, forgot/reset password
│   │   │   ├── logs.py         # Log CRUD
│   │   │   ├── contexts.py     # Context CRUD
│   │   │   ├── tags.py         # Tag CRUD
│   │   │   ├── templates.py    # Template CRUD + samples
│   │   │   ├── recall.py       # AI recall endpoints
│   │   │   ├── chat_history.py # Chat history endpoints
│   │   │   ├── feedback.py     # Feedback submission
│   │   │   ├── admin.py        # Admin dashboard (protected)
│   │   │   └── users.py        # Profile, password update
│   │   └── deps.py             # Shared dependencies (get_db, get_current_user)
│   ├── core/
│   │   ├── config.py           # Settings via pydantic-settings
│   │   ├── security.py         # JWT, password hashing, OAuth, encryption
│   │   └── exceptions.py       # Custom exceptions + handlers
│   ├── db/
│   │   ├── session.py          # Async engine + session factory
│   │   ├── base.py             # SQLAlchemy declarative base
│   │   └── models/             # One model per file
│   │       ├── user.py
│   │       ├── context.py
│   │       ├── log_entry.py
│   │       ├── tag.py
│   │       ├── template.py
│   │       ├── chat_session.py
│   │       ├── chat_message.py
│   │       ├── feedback.py
│   │       └── ai_query_log.py
│   ├── schemas/                # Pydantic request/response
│   │   ├── auth.py
│   │   ├── logs.py
│   │   ├── contexts.py
│   │   ├── tags.py
│   │   ├── templates.py
│   │   ├── recall.py
│   │   └── common.py           # ApiResponse, PaginatedResponse
│   ├── services/               # Business logic
│   │   ├── auth_service.py
│   │   ├── log_service.py
│   │   ├── context_service.py
│   │   ├── tag_service.py
│   │   ├── template_service.py
│   │   ├── recall_service.py
│   │   └── admin_service.py
│   ├── ai/                     # AI/RAG module (isolated)
│   │   ├── embeddings.py       # Embedding generation (sentence-transformers)
│   │   ├── vector_store.py     # Qdrant client wrapper
│   │   ├── llm_provider.py     # LLM adapter (Groq/Ollama — single interface)
│   │   ├── rag_engine.py       # LlamaIndex RAG pipeline
│   │   └── prompts.py          # System prompts, prompt templates
│   ├── workers/                # Celery tasks
│   │   ├── celery_app.py       # Celery configuration
│   │   ├── embedding_tasks.py  # Async embedding after log create/edit
│   │   └── email_tasks.py      # Async email (password reset)
│   └── main.py                 # FastAPI app factory, middleware, startup/shutdown
├── alembic/                    # Migration scripts
├── tests/                      # pytest (mirrors app/ structure)
├── docs/                       # PRD.md, ARCHITECTURE.md, DB_DESIGN.md
├── alembic.ini
├── pyproject.toml
├── Dockerfile
├── Dockerfile.worker
├── docker-compose.yml          # Local dev: API + worker + Postgres + Redis + Qdrant
├── .env.example
└── Makefile
```

**Convention:** Routes thin (validate → service → response). Services contain logic. Models data-only. AI module isolated. One file per entity. Flat structure.

---

## 4. Database Design (PostgreSQL)

9 tables. UUID PKs. TIMESTAMPTZ UTC. AES-256 encrypted log content.

### users

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default uuid4 | |
| username | VARCHAR(50) | UNIQUE, NOT NULL | Login identifier |
| email | VARCHAR(255) | UNIQUE, NULLABLE | NULL for OAuth-only users |
| password_hash | VARCHAR(255) | NULLABLE | NULL for Google OAuth users |
| google_id | VARCHAR(255) | UNIQUE, NULLABLE | Google OAuth subject ID |
| auth_provider | VARCHAR(20) | NOT NULL, DEFAULT 'local' | 'local' or 'google' |
| is_admin | BOOLEAN | NOT NULL, DEFAULT false | Admin dashboard access |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Soft disable |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

### contexts

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| user_id | UUID | FK → users.id, NOT NULL | |
| type | VARCHAR(20) | NOT NULL | 'self', 'teammate', 'project' |
| name | VARCHAR(100) | NOT NULL | 'Self' for self-type |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

**Unique:** (user_id, type, name)

### log_entries

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| user_id | UUID | FK → users.id, NOT NULL | Denormalized for fast queries |
| context_id | UUID | FK → contexts.id, NOT NULL | |
| content_encrypted | TEXT | NOT NULL | AES-256 encrypted at app layer |
| date_type | VARCHAR(10) | NOT NULL | 'daily', 'weekly', 'custom' |
| date_start | DATE | NOT NULL | |
| date_end | DATE | NOT NULL | Same as start for daily |
| is_deleted | BOOLEAN | NOT NULL, DEFAULT false | Soft delete |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

**Indexes:** (user_id, context_id, date_start, date_end), (user_id, is_deleted)

### tags

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| user_id | UUID | FK → users.id, NOT NULL | Per-user tags |
| name | VARCHAR(50) | NOT NULL | |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

**Unique:** (user_id, name). No delete in v1.

### log_entry_tags (join)

| Column | Type | Constraints |
|--------|------|-------------|
| log_entry_id | UUID | FK → log_entries.id, Composite PK |
| tag_id | UUID | FK → tags.id, Composite PK |

### templates

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| user_id | UUID | FK → users.id, NULLABLE | NULL for sample templates |
| name | VARCHAR(100) | NOT NULL | |
| content | TEXT | NOT NULL | |
| is_sample | BOOLEAN | NOT NULL, DEFAULT false | System-provided samples |
| category | VARCHAR(50) | NULLABLE | For samples: 'software_dev', etc. |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

### chat_sessions

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| user_id | UUID | FK → users.id, NOT NULL | |
| context_id | UUID | FK → contexts.id, NULLABLE | Scoped context |
| title | VARCHAR(255) | NULLABLE | Auto-generated from first question |
| time_window_start | DATE | NULLABLE | |
| time_window_end | DATE | NULLABLE | |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

### chat_messages

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| chat_session_id | UUID | FK → chat_sessions.id, NOT NULL | |
| role | VARCHAR(10) | NOT NULL | 'user' or 'assistant' |
| content | TEXT | NOT NULL | |
| created_at | TIMESTAMPTZ | NOT NULL | |

**Index:** (chat_session_id, created_at)

### feedback

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| user_id | UUID | FK → users.id, NOT NULL |
| content | TEXT | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

### ai_query_logs

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| user_id | UUID | FK → users.id, NOT NULL | |
| context_id | UUID | FK → contexts.id, NULLABLE | |
| prompt_preview | VARCHAR(200) | NULLABLE | Truncated. Not full text. |
| tokens_used | INTEGER | NULLABLE | |
| created_at | TIMESTAMPTZ | NOT NULL | |

Used for rate limiting (count/user/day) and admin analytics.

### Database Conventions

- **PKs:** UUID v4 everywhere. Never sequential IDs.
- **Timestamps:** TIMESTAMPTZ in UTC. Frontend converts to local.
- **Soft delete:** Only on log_entries. Everything else: hard delete.
- **Encryption:** content_encrypted = AES-256 at app layer. Key in env var.
- **Migrations:** Alembic. Never modify DB directly.
- **Indexes:** All FKs + commonly queried columns. Composite for multi-column filters.

---

## 5. Authentication Architecture

### 5.1 Strategy

Dual auth: username/password (JWT) + Google OAuth 2.0. Both paths issue same JWT tokens.

### 5.2 JWT Token Design

- **Access token:** 15 min expiry. Contains user_id, username, is_admin. In Authorization: Bearer header.
- **Refresh token:** 7 day expiry. httpOnly secure cookie. Used for silent refresh.
- **Token rotation:** On refresh, both tokens reissued. Old refresh invalidated.

### 5.3 Auth Flows

**Sign Up (local):** username + email + password → bcrypt hash → create user → create 'Self' context → issue tokens → dashboard.

**Log In (local):** username + password → verify → issue tokens.

**Google OAuth:** Frontend OAuth flow → ID token → backend verifies with Google → create user if new → create 'Self' context → issue tokens.

**Forgot Password:** email → generate reset JWT (1hr expiry) → send email via SMTP → user clicks link → new password + token → verify → update hash.

### 5.4 Security

- bcrypt 12 rounds
- HS256 JWT with strong secret from env
- SameSite cookie on refresh tokens
- Rate limit: 5 attempts/min/IP on auth endpoints
- Input validation on all auth fields

---

## 6. AI / RAG Architecture

### 6.1 Embedding Pipeline

**Trigger:** Log created or edited → Celery task dispatched.

**Process:** Decrypt content → generate 384-dim vector (all-MiniLM-L6-v2) → store in Qdrant with metadata (user_id, context_id, log_entry_id, date_start, date_end, tag_ids).

**On edit:** Delete old vector → generate new → store.
**On delete:** Delete vector from Qdrant.

### 6.2 Retrieval Pipeline

1. User selects context + time window + optional tag filters
2. User's question embedded with same model
3. Qdrant similarity search with filters: user_id (mandatory), context_id, date range, tag_ids
4. Top-K results (K=10 default)
5. Retrieved entries decrypted and formatted as LLM context

### 6.3 LLM Query Pipeline

LlamaIndex orchestrates:
1. System prompt: answer only from provided entries, never hallucinate, state when insufficient
2. Retrieved entries injected as context
3. User question sent as query
4. Response stored in chat_messages and returned

### 6.4 LLM Provider Abstraction

```python
class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, context: str) -> str: ...

class GroqProvider(LLMProvider): ...   # v1 — free API
class OllamaProvider(LLMProvider): ... # future — self-hosted
```

Switch: change `LLM_PROVIDER` env var. No other code changes.

### 6.5 Qdrant Configuration

- Single collection, user_id as filter (not collection-per-user)
- Payload: user_id (keyword), context_id (keyword), log_entry_id (keyword), date_start (integer/epoch), date_end (integer/epoch), tag_ids (keyword array)
- Vector: 384 dimensions, Cosine similarity

### 6.6 Rate Limiting

50 AI queries/user/day. Tracked in ai_query_logs. Returns 429 when exceeded.

---

## 7. API Design

### 7.1 Endpoints

**Auth:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/auth/signup | Register |
| POST | /api/v1/auth/login | Login |
| POST | /api/v1/auth/google | Google OAuth token exchange |
| POST | /api/v1/auth/forgot-password | Request reset email |
| POST | /api/v1/auth/reset-password | Reset with token |
| POST | /api/v1/auth/refresh | Refresh access token |
| POST | /api/v1/auth/logout | Invalidate refresh token |

**Contexts:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/contexts | List user's contexts |
| POST | /api/v1/contexts | Create teammate/project |
| PATCH | /api/v1/contexts/{id} | Rename |

**Logs:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/logs | List (filters: context_id, date range, tags) |
| GET | /api/v1/logs/{id} | Get single entry |
| POST | /api/v1/logs | Create |
| PATCH | /api/v1/logs/{id} | Update |
| DELETE | /api/v1/logs/{id} | Soft delete |
| GET | /api/v1/logs/calendar/{year}/{month} | Calendar data |

**Tags:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/tags | List user's tags |
| POST | /api/v1/tags | Create |
| PATCH | /api/v1/tags/{id} | Rename |
| POST | /api/v1/logs/{id}/tags | Assign tags to log |

**Templates:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/templates | List (custom + sample) |
| POST | /api/v1/templates | Create custom |
| PATCH | /api/v1/templates/{id} | Update custom |
| DELETE | /api/v1/templates/{id} | Delete custom |

**Recall:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/recall/query | Ask AI question |
| GET | /api/v1/recall/chats | List chat history |
| GET | /api/v1/recall/chats/{id} | Get full chat session |

**Other:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/feedback | Submit feedback |
| PATCH | /api/v1/users/me | Update profile |
| PATCH | /api/v1/users/me/password | Update password |
| GET | /api/v1/admin/stats | Admin metrics |
| GET | /api/v1/admin/feedback | Admin feedback list |

### 7.2 Conventions

- **Response envelope:** `{ "data": ..., "message": "...", "success": true/false }`
- **Paginated:** `{ "data": [...], "total": N, "page": N, "page_size": N }`
- **Error:** `{ "success": false, "message": "...", "error_code": "VALIDATION_ERROR", "details": [...] }`
- **Status codes:** 200, 201, 204, 400, 401, 403, 404, 429, 500
- **Pagination:** ?page=1&page_size=20 (default 20, max 100)
- **Filtering:** ?context_id=xxx&date_from=2026-01-01&date_to=2026-03-31&tag_ids=xxx,yyy

---

## 8. Deployment Architecture

| Component | Service | Tier | Notes |
|-----------|---------|------|-------|
| Frontend | Vercel | Free | Auto-deploy. Custom domain. CDN. |
| Backend API | Render | Free | Docker. Cold start ~30-50s. |
| Celery Worker | Render | Free | Background Worker service. Same image, different command. |
| PostgreSQL | Neon | Free (512MB) | Serverless. Auto-suspend 5min. |
| Qdrant | Qdrant Cloud | Free (1GB) | Managed. Always on. |
| Redis | Redis Cloud | Free (30MB) | Celery broker + rate limiting. |
| LLM | Groq | Free (30 RPM) | Llama 3.1 8B. |

### Docker

- `Dockerfile` — FastAPI app. Pre-loads embedding model at build time.
- `Dockerfile.worker` — Celery worker. Same base, different entrypoint.
- `docker-compose.yml` — Local dev: API + worker + Postgres + Redis + Qdrant.

### CI/CD (GitHub Actions)

**mylogmate-web:** push to main → ESLint → tsc → Vitest → build → Vercel auto-deploys.
**mylogmate-api:** push to main → ruff → mypy → pytest → Docker build → Render auto-deploys.
PRs: lint + typecheck + test only.

### Environment Variables

| Variable | Used By | Description |
|----------|---------|-------------|
| DATABASE_URL | Backend | Neon PostgreSQL connection |
| QDRANT_URL | Backend | Qdrant Cloud URL |
| QDRANT_API_KEY | Backend | Qdrant API key |
| REDIS_URL | Backend + Worker | Redis Cloud connection |
| JWT_SECRET_KEY | Backend | JWT signing secret |
| ENCRYPTION_KEY | Backend + Worker | AES-256 key for log content |
| GROQ_API_KEY | Backend | Groq LLM API key |
| LLM_PROVIDER | Backend | 'groq' or 'ollama' |
| GOOGLE_CLIENT_ID | Backend + Frontend | OAuth client ID |
| GOOGLE_CLIENT_SECRET | Backend | OAuth client secret |
| SMTP_HOST / SMTP_USER / SMTP_PASSWORD | Worker | Gmail SMTP |
| VITE_API_URL | Frontend | Backend API base URL |

---

## 9. Security Architecture

- **Transit:** HTTPS everywhere. Vercel/Render provide TLS.
- **At rest:** AES-256 encrypted log content. Key in env var.
- **Passwords:** bcrypt 12 rounds.
- **JWT:** Short-lived access (15min). httpOnly refresh. Rotation on refresh.
- **CORS:** Strict origin whitelist — only Vercel frontend domain.
- **Rate limiting:** slowapi. Auth: 5/min. AI: 50/day.
- **Input validation:** Pydantic on all input. No raw user input to DB.
- **SQL injection:** SQLAlchemy parameterized queries only.
- **XSS:** React auto-escapes. No dangerouslySetInnerHTML.
- **Prompt injection:** User queries as user messages only. System prompt fixed.
- **Data isolation:** Every query includes user_id filter. Qdrant queries filter by user_id.

---

## 10. Background Jobs (Celery)

| Task | Trigger | Action |
|------|---------|--------|
| generate_embedding | Log created/edited | Decrypt → embed → upsert Qdrant |
| delete_embedding | Log deleted | Remove from Qdrant |
| send_password_reset_email | Forgot password | Send via SMTP |

**Config:** Redis broker. Acks late. 3 retries with exponential backoff (30s/60s/120s). No result backend.

---

## 11. Observability

### Logging (structlog)

**Logged:** API requests (method, path, status, duration), auth events, AI queries (context, tokens, latency), Celery tasks, errors with stack traces.

**NOT logged:** User content, prompts, AI responses, passwords, tokens.

### Health Endpoints

- `GET /health` — API process running. Used by Render.
- `GET /ready` — Checks PostgreSQL + Qdrant + Redis connectivity.

### Admin Dashboard

Protected /admin route. Backend /api/v1/admin/ (requires is_admin). Shows: total users, active users, log entries, AI queries/day, recent feedback, system health.

---

## 12. Scaling Strategy

| Bottleneck | Solution | Cost |
|------------|----------|------|
| Render cold starts | Upgrade to paid ($7/mo) | $7/mo |
| Neon 512MB | Upgrade to Launch ($19/mo) | $19/mo |
| Qdrant 1GB | Upgrade tier or self-host | $0-25/mo |
| Groq 30 RPM | Add Ollama overflow or upgrade Groq | $0+ |
| Redis 30MB | Upgrade tier ($5/mo) | $5/mo |
| Celery capacity | Scale Render workers | $7+/mo |
| LLM quality | Better model (70B on GPU, or Claude/GPT API) | Variable |

**Key principle:** Every scaling step is config/tier change, not architecture rewrite.

---

## 13. Engineering Conventions

### Code Style

- **Python:** Ruff lint + format. Strict type hints. mypy. 88 char line limit.
- **TypeScript:** ESLint + Prettier. Strict tsconfig. No `any`. Explicit return types.
- **Naming:** Python: snake_case. TypeScript: camelCase vars, PascalCase components/types.

### Git

- **Branches:** main (production) + feature branches. No develop branch.
- **Branch naming:** feat/add-tags-crud, fix/auth-token-refresh, chore/update-deps
- **Commits:** Conventional Commits: `feat: add tag CRUD endpoints`
- **PRs:** Even solo — feature branch → PR → CI green → merge to main.

### Testing

- **Backend:** pytest. All endpoints (happy + error). Mock externals (Groq, Qdrant).
- **Frontend:** Vitest + RTL. Component rendering + interactions. Mock API.
- **Priority:** API endpoints first → critical business logic → UI tests last.

### Makefile

```
make dev          # docker-compose up
make test         # pytest
make lint         # ruff check + mypy
make migrate      # alembic upgrade head
make migration    # alembic revision --autogenerate
make seed         # sample templates + admin user
make shell        # python shell with app context
```

---

## 14. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)

- Backend: Project setup, Docker Compose, FastAPI scaffold, SQLAlchemy models, Alembic, Pydantic schemas
- Backend: Auth endpoints (signup, login, Google OAuth, JWT, refresh, forgot/reset password)
- Frontend: Project setup, Vite + Tailwind, design tokens, base components
- Frontend: Landing page, auth screens, routing, auth state
- CI/CD: GitHub Actions for both repos

### Phase 2: Core Logging (Week 3-4)

- Backend: Context CRUD, Log CRUD, Tag CRUD, Template CRUD + seed samples
- Backend: Celery + Redis, embedding generation task, Qdrant setup, vector pipeline
- Frontend: Home screen, Log flow (context → date → entry + tags + voice + templates), Sidebar
- Frontend: Context management screens (Teammates, Projects, Tags, Templates)

### Phase 3: AI Recall (Week 5-6)

- Backend: LlamaIndex, Groq provider, RAG pipeline, recall/query endpoint
- Backend: Chat sessions + messages, chat history endpoints
- Frontend: Recall flow (year → month → calendar + logs), AI prompt bar, chat overlay, chat history
- Integration testing: log → embed → query → response E2E

### Phase 4: Polish & Ship (Week 7-8)

- Backend: Admin endpoints, feedback, rate limiting, health checks
- Frontend: Admin dashboard, feedback modal, settings, loading/error/empty states
- Frontend: Mobile responsive pass
- Deploy: Vercel + Render + Neon + Qdrant Cloud + Redis Cloud
- Seed data, smoke testing, QA, launch

---

**This architecture is LOCKED. Begin Phase 1 implementation.**
