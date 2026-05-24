# MyLogMate — Claude Code Master Prompt

**Copy everything below the line and paste as your first message in Claude Code.**

---

## Context

I'm building MyLogMate — a production-grade work-logging + AI-recall web application. This is a solo indie project but must be built with the quality of a senior engineer's portfolio piece — clean architecture, proper separation of concerns, comprehensive error handling, type safety, and thorough testing. NOT vibe-coded throwaway code.

All product requirements, technical architecture, and design system specs are in the `docs/` folder. Read them fully before writing any code:

- `docs/PRD.md` — Full product requirements, features, user flows
- `docs/ARCHITECTURE.md` — Tech stack, DB schema, API design, deployment, conventions
- `docs/DESIGN_SYSTEM.md` — Colors, components, typography, spacing, responsive patterns (frontend repo only)

The `.claude/` folder contains skills, rules, agents, hooks, and commands that define exactly how code should be written for this project. Familiarize yourself with them — they encode architecture conventions, patterns, and quality gates.

## Design Reference

Fetch this design file, read its readme, and implement the relevant aspects of the design:
https://api.anthropic.com/v1/design/h/K_t7QAMX9bA3SjqwAwMhuw?open_file=MyLogMate.html
Implement: MyLogMate.html

This is the Claude Design handoff containing all UI screens. When building frontend components and pages, match the design intent from this bundle — layout structure, component hierarchy, spacing, colors, and interaction patterns. The `docs/DESIGN_SYSTEM.md` file supplements this with explicit token values and responsive rules.

## Tech Stack (Locked)

**Backend (mylogmate-api):**
- Python 3.12 + FastAPI + Pydantic v2
- SQLAlchemy 2.0 async + Alembic migrations
- PostgreSQL 16 (Neon free tier) — relational data
- Qdrant Cloud (free tier) — vector embeddings + server-side embedding via Cloud Inference (free models, no local model needed)
- Redis Cloud (free 30MB) — Celery broker + rate limiting
- Celery — async tasks (embedding generation, emails)
- LlamaIndex — RAG orchestration
- Groq API free tier — LLM (Llama 3.1 8B) with modular adapter for Ollama swap
- Custom JWT (access 15min + refresh 7d httpOnly) + Google OAuth 2.0
- Gmail SMTP — password reset emails only
- structlog — structured JSON logging
- Docker + Docker Compose — local dev
- pytest + httpx — testing

**Frontend (mylogmate-web):**
- React 18 + TypeScript + Vite
- Tailwind CSS (design tokens in tailwind.config.ts)
- React Router v6 (lazy loading all pages)
- Zustand — state management
- Axios — API client with interceptors (token refresh, error handling)
- lucide-react — icons (ONLY icon library allowed)
- Vitest + React Testing Library — testing

**Hosting (when ready):**
- Frontend: Vercel (free)
- Backend API: Render (free, accepts cold starts)
- Celery Worker: Render Background Worker (free)
- PostgreSQL: Neon (free 512MB)
- Qdrant: Qdrant Cloud (free 1GB + free Cloud Inference for embeddings)
- Redis: Redis Cloud (free 30MB)
- LLM: Groq API (free 30 RPM)
- Uptime ping: UptimeRobot (free) hitting /health every 5min

## Key Technical Decision: Qdrant Cloud Inference (Server-Side Embeddings)

Qdrant Cloud provides free server-side embedding generation via Cloud Inference. This means we do NOT need to run any embedding model locally — no sentence-transformers, no FastEmbed, no ONNX, no PyTorch. Qdrant Cloud handles embedding generation inside their infrastructure.

Why this matters:
- Zero RAM usage for embeddings on our Render backend (huge win for free tier)
- No model download at Docker build time (faster builds, smaller images)
- No cold-start delay from model loading
- Free with no token limits on selected models (all-MiniLM-L6-v2 is free)
- Embedding happens server-side when upserting/querying — we just send raw text

Usage pattern (use context7 MCP to fetch current Qdrant Cloud Inference docs before implementing):
```python
from qdrant_client import QdrantClient, models

client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)

# Upsert with server-side embedding — send text, Qdrant embeds it
client.upsert(
    collection_name="log_entries",
    points=[
        models.PointStruct(
            id=log_entry_id,
            vector=models.Document(text=decrypted_content, model="Qdrant/bge-small-en-v1.5"),
            payload={"user_id": str(user_id), "context_id": str(context_id), ...}
        )
    ]
)

# Query with server-side embedding — send query text, Qdrant embeds + searches
results = client.query_points(
    collection_name="log_entries",
    query=models.Document(text="What were my achievements?", model="Qdrant/bge-small-en-v1.5"),
    query_filter=Filter(...),
    limit=10
)
```

IMPORTANT: The exact API for Cloud Inference may differ from above — ALWAYS use context7 MCP to fetch current Qdrant documentation before writing any Qdrant code. The key point is: we send plain text, Qdrant does the embedding server-side.

Update the architecture accordingly:
- Remove sentence-transformers and fastembed from dependencies entirely
- The Celery embedding task now sends decrypted text to Qdrant Cloud (which embeds it) instead of generating vectors locally
- No embedding model needs to be loaded anywhere in our code
- Docker images are much smaller and lighter
- Collection config: use the free model available in Qdrant Cloud Inference (check the Inference tab in Qdrant Cloud Console for current free models)

## Development Approach

### Phase 1: Foundation — START HERE

**Step 1: Database Design**
Before writing any code, design the complete database schema. Read `docs/ARCHITECTURE.md` section 4 for the initial schema, but treat it as a starting point — review it critically, identify any gaps or improvements, and produce the final `docs/DB_DESIGN.md` with:
- Complete table definitions with all columns, types, constraints, and indexes
- Entity relationship diagram (Mermaid syntax)
- Justification for any changes from the initial schema
- Sample seed data for templates (6 role-based samples as defined in PRD)

Do NOT proceed to code until I review and approve the DB design.

**Step 2: Project Scaffolding**
After DB design approval:
- Initialize the project structure exactly as defined in `docs/ARCHITECTURE.md` section 3.2
- Set up pyproject.toml with all dependencies
- Configure Docker Compose (FastAPI + Celery worker + PostgreSQL + Redis + Qdrant)
- Create Makefile with all commands
- Set up .env.example with all required variables
- Configure ruff, mypy, pytest
- Create the FastAPI app factory (main.py) with middleware, CORS, exception handlers, startup/shutdown events
- Create health + ready endpoints

**Step 3: SQLAlchemy Models + Alembic**
- Create all ORM models matching the approved DB design
- Set up Alembic and generate the initial migration
- Test: `alembic upgrade head` creates all tables correctly

**Step 4: Pydantic Schemas**
- Create all request/response schemas
- ApiResponse envelope, PaginatedResponse, ErrorResponse
- Field validation with proper constraints

**Step 5: Auth System**
- JWT token creation/validation (access + refresh)
- Password hashing (bcrypt)
- Google OAuth token verification
- Auth dependencies (get_current_user, get_admin_user)
- Auth routes: signup, login, google, refresh, logout, forgot-password, reset-password
- Auto-create "Self" context on signup
- Unit tests for all auth endpoints

COMMIT after Step 5 with: `feat: implement auth system with JWT + Google OAuth`

### Phase 2: Core Features

**Step 6: Context CRUD** — routes, schemas, service, tests
**Step 7: Tag CRUD** — routes, schemas, service, tests
**Step 8: Log Entry CRUD** — routes, schemas, service, encryption, tests
**Step 9: Template CRUD + seed samples** — routes, schemas, service, seeder, tests
**Step 10: Calendar endpoint** — /logs/calendar/{year}/{month}, tests

COMMIT after each step with descriptive conventional commit messages.

### Phase 3: AI / RAG

**Step 11: Qdrant setup** — collection creation, FastEmbed config, vector store wrapper
**Step 12: Celery tasks** — embedding generation (create/edit/delete), email sending
**Step 13: LLM provider abstraction** — Groq adapter + Ollama adapter interface
**Step 14: RAG pipeline** — LlamaIndex integration, recall query endpoint, prompts
**Step 15: Chat sessions** — chat session + message storage, history endpoints, tests

### Phase 4: Admin + Polish

**Step 16: Admin endpoints** — stats, feedback list, user list
**Step 17: Feedback endpoint** — submit feedback
**Step 18: Rate limiting** — slowapi on auth (5/min) and AI (50/day)
**Step 19: CI/CD** — GitHub Actions workflow (lint + typecheck + test)

### Frontend (after backend API is stable)

**Step 20: Project setup** — Vite + Tailwind + design tokens + base components (Button, Card, Input, Modal, Sidebar)
**Step 21: Auth pages** — Landing, Login, Signup, Forgot/Reset Password + auth store + API client
**Step 22: App shell** — AppLayout with sidebar, routing with AuthGuard/AdminGuard
**Step 23: Home + Log flow** — Dashboard, context selection, log creation with tags + voice + templates
**Step 24: Recall flow** — Year/month/calendar, log browsing, AI prompt bar, chat overlay
**Step 25: Management pages** — Teammates, Projects, Tags, Templates, Chat History, Settings, Feedback
**Step 26: Admin dashboard** — Charts (Recharts), users table, feedback, health
**Step 27: Responsive pass** — Mobile optimization across all screens
**Step 28: Dark mode** — Apply dark mode tokens to all components

### Deployment

**Step 29: Deploy backend** — Render (API + worker), Neon, Qdrant Cloud, Redis Cloud, env vars
**Step 30: Deploy frontend** — Vercel, connect to production API
**Step 31: Smoke test** — End-to-end flow on production
**Step 32: UptimeRobot** — Set up /health ping every 5min

## Code Quality Rules (Non-Negotiable)

### Backend
- Type hints on ALL function signatures (params AND return types)
- async def for all route handlers and service methods
- Routes are THIN: validate → service → ApiResponse. Zero business logic in routes.
- Every DB query MUST filter by user_id. Data isolation is non-negotiable.
- Log content MUST be AES-256 encrypted before DB write, decrypted after read. NEVER plain text in DB.
- Pydantic validation on ALL request inputs. No raw data reaches the database.
- Every endpoint must have unit tests: happy path + 401 (unauthorized) + 422 (validation) + 404 minimum.
- Mock ALL externals in tests: Groq, Qdrant, SMTP, Celery.
- structlog for all logging. NEVER log passwords, tokens, decrypted content, or user prompts.
- All prompts centralized in app/ai/prompts.py. No inline prompt strings anywhere.
- Conventional Commits format for all commit messages.

### Frontend
- Strict TypeScript. No `any` type. Ever. Explicit return types on all functions.
- Every component supports dark mode (dark: Tailwind classes).
- Design tokens from tailwind.config.ts. NEVER hardcode hex colors in components.
- All interactive elements: default, hover, active, focus, disabled states.
- Every data page: loading skeleton + empty state + error state + data state. All four.
- lucide-react icons ONLY. No other icon library.
- Tailwind ONLY. No CSS files. No inline styles. No styled-components.
- API calls through Zustand stores or api/ functions. NEVER directly in components.
- Access token in Zustand memory only. Refresh token in httpOnly cookie. NEVER localStorage for tokens.

## Commit Workflow

After completing each logical unit of work:
1. Run linting (ruff check + mypy for backend, ESLint + tsc for frontend)
2. Run tests (pytest for backend, vitest for frontend)
3. Fix any failures
4. Stage all changes
5. Suggest a Conventional Commit message
6. Show me the staged diff summary and commit message — DO NOT commit. Wait for my approval.

## Important

- Use context7 MCP to fetch current library documentation before generating code that depends on specific API signatures (FastAPI, SQLAlchemy, LlamaIndex, Qdrant, Tailwind, React Router, etc.)
- Read the relevant .claude/skills/ before writing code in any module
- Never commit .env files, secrets, or API keys
- Never auto-commit. Always wait for my approval.

## Start Now

Begin with **Step 1: Database Design**. Read `docs/ARCHITECTURE.md` section 4, analyze the schema critically, and produce the final `docs/DB_DESIGN.md`. Wait for my approval before proceeding to Step 2.