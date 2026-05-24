# MyLogMate — Product Requirements Document

**Version:** 1.0 Final | **Date:** May 2026 | **Author:** Vamsi | **Status:** Final

> *Log once. Recall anytime.*

---

## 1. Overview

### 1.1 Product Summary

MyLogMate is a free, privacy-first web application that helps working professionals document their work on a daily, weekly, or monthly basis and use AI to get custom answers, summaries, and insights from their own logged data. Users log their work under three contexts — Self, Teammate, or Project — and later query their data using natural language to get accurate, personalized responses grounded 100% in their own logs.

Whether it's preparing for a quarterly review, recalling what a teammate contributed, or summarizing a project's progress, MyLogMate turns raw work entries into ready answers.

### 1.2 Vision

To become the simplest, most trusted tool for professionals to never lose track of their work again. MyLogMate ensures that when review season arrives, users walk in fully prepared — with accurate, comprehensive, and organized information about their contributions. Built as a solo indie product with the ambition of an industry-grade platform.

### 1.3 Builder's Intent

This product is being built as a one-person indie project with multiple goals:

- Build an industry-grade product end to end as a solo developer
- Gain deep hands-on experience with AI/RAG systems
- Learn the full product lifecycle (design, development, deployment, marketing, growth)
- Experience the entrepreneurial journey similar to YC-style founders — from idea to real users

---

## 2. Problem Statement

Performance reviews are a universal experience for professionals across IT, finance, healthcare, and virtually every industry. Yet the preparation process is broken:

- **Recall bias:** Most professionals rely on memory. Recent work gets overrepresented while earlier contributions are forgotten.
- **Scattered documentation:** Those who do document use scattered notes, Slack messages, or personal docs with no structure.
- **Time-consuming synthesis:** Manually reading through months of notes and categorizing them by skills, achievements, and challenges is tedious and error-prone.
- **No habit formation:** Without a dedicated, simple tool, the friction of documenting work is too high.
- **Missed recognition:** Important achievements, learnings, and contributions are lost simply because they were not captured or surfaced at the right time.

### 2.1 Why Not Existing Tools?

- **Habit gap:** Most people don't have a logging habit at all. MyLogMate makes logging frictionless.
- **Manual synthesis:** Even if someone logs in a notes app, they still have to manually organize entries by theme. MyLogMate does this automatically with AI.
- **Purpose-built:** General note apps aren't designed for performance review preparation.
- **Privacy:** MyLogMate stores data in a way that even the developer cannot trivially read user content.

---

## 3. Target Audience

### Primary Users

- Software engineers, designers, product managers, and other IT professionals who undergo periodic performance reviews
- Team leads and managers who want to document observations about their team members
- Any professional who wants to build a consistent work-logging habit

### Secondary Users

- Professionals in non-IT industries (finance, consulting, healthcare, education) with structured review cycles
- Freelancers and contractors who want to maintain a work log for client reporting
- Companies that want employees to have a lightweight, secure work-logging tool

---

## 4. Core Concepts

### 4.1 Contexts

Every log entry belongs to exactly one context. A context determines the subject of the log:

| Context | Description | Example |
|---------|-------------|---------|
| Self | Logs about the user's own work, learnings, achievements, and reflections | "Completed the migration script and deployed to staging." |
| Teammate | Logs about a specific teammate's work or behavior, from the user's perspective. Users can create multiple teammate profiles. | "Rahul handled the client escalation really well today." |
| Project | Logs about a specific project's progress, milestones, decisions, or blockers. Users can create multiple project profiles. | "Project Alpha: finalized the API contract with the payments team." |

**Key rules:**

- A user can create unlimited Teammate and Project contexts
- Each log entry is tagged to exactly one context at creation
- AI queries are always scoped to a selected context and time window

### 4.2 Log Entries

A log entry is the atomic unit of data in MyLogMate. It is free-form text that the user writes to document work. Each entry has:

- The text content
- A context tag (Self / Teammate name / Project name)
- A timestamp (auto-set, optionally editable)
- Optional date override for backdating
- Optional tags for categorization
- A date scope: single day, a week range, or a custom date range

### 4.3 Tags

Tags are user-defined labels that can be attached to log entries for organization, filtering, and scoped recall.

- **Adding tags:** Each log entry has a tag icon. Clicking it shows existing tags to select from, and a text input to type a new tag name. If the typed name doesn't match, a "Create tag" option appears inline.
- **Editing tags:** Users can rename or delete tags from the same inline interface. Deleting a tag removes it from all associated entries.
- **Tags in Recall:** When querying with AI, users can optionally filter by tags — include specific tags, exclude specific tags, or leave unfiltered.

### 4.4 AI Recall System

The Recall section is where users ask questions and get AI-generated answers from their logged data. Uses RAG with an open-source LLM to generate answers grounded exclusively in the user's own logs.

**Before asking a question, the user must provide:**

- Context: which Self / Teammate / Project to search
- Time window: Last 7 days, Last 30 days, or Custom date range
- Optional tag filters: include or exclude specific tags

**Users can ask questions in two ways:**

- **One-click prompts:** Suggested buttons like "Key achievements," "Skills learned," "Challenges faced," "Summary of work," "Areas of improvement."
- **Custom prompt:** Free-text input for any question against scoped data

The AI answers only based on retrieved log entries and clearly states when information is insufficient. No hallucination.

---

## 5. User Flows

### 5.1 Onboarding

User visits landing page → reads product description and tutorial steps (Log → Ask → Get Answers) → clicks "Get Started" → signs up or logs in → lands on dashboard.

### 5.2 Logging Work

From dashboard → select context (Self, or pick a Teammate/Project, or create new) → write log entry → optionally adjust date, set date range, add tags → submit. Entry is encrypted and stored.

### 5.3 Viewing and Editing Past Logs

Calendar-based interface within Recall section: select context → see year cards → click year for month cards → click month for calendar view (logged dates visually filled, continuous fill for multi-day entries) → click date slides calendar left, shows entries on right with view/edit/delete options.

### 5.4 Recalling with AI

Recall section combines browsing and AI querying. Sticky prompt bar at bottom (minimizable to floating icon). Set filters: context + time window + optional tags. Type/speak question or pick suggested prompt. AI response appears above input. Follow-up questions within same scoped session.

### 5.5 Managing Contexts

Create, rename, or delete Teammate and Project contexts at any time. Deleting prompts confirmation (removes all associated entries and embeddings). Self context is permanent.

---

## 6. Feature Specifications

### 6.1 Authentication & Security

| Requirement | Details |
|-------------|---------|
| Secure Authentication | Email + password with hashed storage. Google OAuth. |
| Data Encryption in Transit | All API calls over HTTPS/TLS. |
| Data at Rest | Log entries stored encrypted (AES-256). Not plain text in DB. |
| Privacy Guarantee | Developer cannot casually read user data from the database. |
| Session Management | JWT-based sessions with access (15min) + refresh (7d) tokens. |

### 6.2 Log Entry Management

| Feature | Details |
|---------|---------|
| Create Entry | Free-form text. Context required. Auto-timestamped with optional date override. Single-day, week-range, or custom date range. |
| View Entries | Calendar-based browsing: year → month → calendar grid with filled dates. |
| Edit Entry | Edit text and tags. Edited entries are re-embedded. |
| Delete Entry | Soft delete with confirmation. Associated embeddings removed. |
| Tags | Inline tag management: assign, create, rename, delete. Used for filtering in recall. |
| Logging Tips | Minimal section showing sample formats. Optional guidance. |
| Search Logs | **Not in v1.** Planned for future (requires fuzzy search). |

### 6.3 AI Recall Engine

| Feature | Details |
|---------|---------|
| Context Selection | Must select exactly one context before querying. |
| Time Window | Last 7 days, Last 30 days, Custom date range. |
| Tag Filters | Optional: include, exclude, or no filter. |
| Suggested Prompts | "Key achievements," "Skills learned," "Challenges faced," "Summary of work," "Areas of improvement." |
| Custom Prompt | Free-text + voice input. |
| Chat-style UI | Sticky prompt bar at bottom. Minimizable to floating icon. Response area above. |
| RAG Pipeline | LLM via Groq API (free). Embeddings at log creation. Retrieval scoped by context + time + tags. |
| Rate Limiting | 50 AI queries/user/day for v1. |

### 6.4 Context Management

| Feature | Details |
|---------|---------|
| Self Context | Auto-created at signup. Cannot be deleted or renamed. |
| Teammate Contexts | Unlimited. Has name. Can rename or delete. |
| Project Contexts | Unlimited. Has name. Can rename or delete. |
| Deletion Behavior | Deletes all associated entries + embeddings. Requires confirmation. |

### 6.5 Landing Page

| Element | Details |
|---------|---------|
| Logo | MyLogMate branding, clean and minimal. |
| Product Description | Short, clear description. |
| How It Works | 3-step visual: Log → Ask → Get Answers. |
| CTA | "Get Started" button. |
| Demo Video | Thumbnail with play button in hero. 2 min demo. 16:9, max 640-720px. |
| Design | Black/white base + soft blue accent. Google-card-style rounded design. |

### 6.6 Templates

| Feature | Details |
|---------|---------|
| Sample Templates | 6 role-based read-only templates (software dev, team manager, etc.). Seeded on first run. |
| Custom Templates | Users can create, edit, delete their own templates. |
| Use in Logging | "Use template" picker available in log entry screen. |

### 6.7 Admin Dashboard

| Feature | Details |
|---------|---------|
| Route | Hidden /admin route. Only visible if user.is_admin. |
| Metrics | Signups over time, active users, total logs, AI queries/day, most active users. |
| Charts | 3 Recharts charts (signups, AI queries/day, most active users). |
| Tables | Users table (sortable/searchable). Feedback list. |
| Health | System health indicators (DB, Qdrant, Redis). |

---

## 7. Recall Section — UI Behavior

### 7.1 Layout

- **Top:** Context selector (Self / Teammate / Project)
- **Main area:** Year cards (rounded) → click year for month cards → click month for calendar view
- **Calendar view:** Filled dates for logged entries. Multi-day = continuous fill. Click date slides calendar left, shows entries on right.
- **Bottom (sticky):** Prompt input bar with text input, voice, filter controls. Minimizable to floating icon.

### 7.2 Asking Questions

Expand prompt bar → set filters (time window, tags) → type/speak question or pick suggested prompt → AI response appears above → follow-up questions in same scoped session.

---

## 8. Non-Functional Requirements

### 8.1 Cost & Hosting

- Zero cost for v1. All infrastructure within free tiers.
- No paid APIs. Free LLM tier (Groq).
- Free for users now. Small paid tier possible in future purely for server costs.

### 8.2 Performance

- Log creation: under 500ms perceived latency
- AI queries: under 10 seconds
- Fast page loads. Minimize bundle size.

### 8.3 Responsiveness

- Fully responsive: mobile, tablet, desktop
- Mobile is first-class citizen
- No separate mobile app — responsive web is sufficient

### 8.4 Design System

- **Colors:** Black/white base + soft blue accent (#93B5FF light, #6B9FFF dark)
- **Component style:** Google-card-inspired rounded design (NotebookLM, YouTube Shorts)
- **Interaction states:** Visible hover, focus, active on all interactive elements
- **Dark mode:** Full dark mode support, togglable. Required, not nice-to-have.
- **Typography:** Clean sans-serif. Consistent sizing hierarchy.
- **Principle:** Every screen self-explanatory. Minimal learning curve. Real product feel.

### 8.5 Security & Abuse Prevention

| Measure | Details |
|---------|---------|
| Rate Limiting | API-level on all endpoints. Stricter on AI queries. |
| Input Validation | All inputs sanitized. XSS, SQL injection, prompt injection protection. |
| Auth Security | bcrypt passwords. Secure JWT tokens. CSRF protection. |
| DDoS Protection | Hosting provider built-in. Cloudflare free if needed. |
| Abuse Monitoring | Log unusual patterns. Manual review capability. |
| Cost Protection | LLM via free API + rate limits prevent runaway usage. |

---

## 9. Information Architecture

| Page/Screen | Description |
|-------------|-------------|
| Landing Page | Product description, how-it-works, CTA, demo video |
| Login / Signup | Email + password + Google OAuth |
| Dashboard | Context selector, quick-add log, recent entries |
| Log Entry View | Calendar-based browsing in Recall section |
| Recall | Browsing + AI query. Year/month/calendar. Sticky prompt bar. |
| Teammates | List, create, rename teammate contexts |
| Projects | List, create, rename project contexts |
| Tags | List, create, rename tags |
| Templates | Custom + sample templates. CRUD. |
| Chat History | Past AI conversations |
| Settings | Dark mode toggle, account settings |
| Feedback | In-app feedback submission |
| Admin Dashboard | Metrics, charts, users, feedback, health (hidden route) |

---

## 10. Data Model (High Level)

| Entity | Key Fields | Notes |
|--------|-----------|-------|
| User | id, username, email, password_hash, google_id, auth_provider, is_admin, is_active | One account per user |
| Context | id, user_id, type, name | Self auto-created. Teammate/Project user-created. |
| LogEntry | id, user_id, context_id, content_encrypted, date_type, date_start, date_end, is_deleted | Core unit. Content AES-256 encrypted. |
| Tag | id, user_id, name | User-defined labels. Shared across contexts. |
| LogEntryTag | log_entry_id, tag_id | Many-to-many join. |
| Template | id, user_id, name, content, is_sample, category | Samples seeded. Custom user-created. |
| ChatSession | id, user_id, context_id, title, time_window_start, time_window_end | Scoped AI chat session. |
| ChatMessage | id, chat_session_id, role, content | 'user' or 'assistant' messages. |
| Feedback | id, user_id, content | User feedback. |
| AIQueryLog | id, user_id, context_id, prompt_preview, tokens_used | Rate limiting + analytics. No sensitive content. |

---

## 11. AI / RAG Architecture (High Level)

### Embedding Generation

- On log create/edit → embed text using all-MiniLM-L6-v2 (384-dim) → store in Qdrant with metadata

### Retrieval

- Embed user query → Qdrant similarity search filtered by user_id + context_id + time window + tags → Top-K results

### Generation

- Retrieved entries → LLM (Groq free tier, Llama 3.1 8B) via LlamaIndex → grounded response → stored in chat_messages

### Key Constraints

- Zero cost: free LLM API + free vector DB
- Accuracy: answers grounded in user data only. No hallucination.
- Scalability: simple architecture for hundreds of users initially

---

## 12. Future Features (Post V1)

| Feature | Priority |
|---------|----------|
| Email Reminders (daily/weekly nudges + periodic summaries) | High |
| Fuzzy Search (keyword search across logs) | High |
| Export / Download (PDF or plain text) | Medium |
| Tagging Analytics (usage patterns, distribution) | Medium |
| Analytics Dashboard (entries/week, active contexts) | Low |
| Team Plan / Subscription (covers server costs only) | Low |
| Collaboration / Sharing (share summaries with managers) | Low |

---

## 13. Business Model

- **Free for all users.** No paywalls, no feature gating, no ads.
- **Future paid tier (optional):** Small subscription for power users or teams to cover server costs. Not for profit.
- **Revenue is not a success metric.** Success = user engagement, retention, and genuine value.

---

## 14. Success Metrics

- **Adoption:** Signups via organic growth (content marketing, social, word of mouth)
- **Retention:** % users logging at least once/week after first month
- **Logging consistency:** Average entries/user/week
- **AI usage:** Recall queries/user (indicates AI is delivering value)
- **Review season spike:** Increase in AI queries during review periods (EOQ, half-year, year-end)
- **User feedback:** Qualitative via in-app feedback

---

## 15. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| LLM quality is poor | Extensive testing. Strong system prompts. Show source entries alongside answers. |
| Free hosting limits exceeded | Minimal resource design. Monitor. Migration plan to low-cost tier. |
| Users don't log consistently | Frictionless logging. Reminders (v2). Logging tips in UI. |
| Encryption adds complexity | Encrypt/decrypt at service layer. Cache in memory during request only. |
| Solo developer bottleneck | Keep v1 scope small. Ship MVP fast. Iterate on real usage. |
| Abuse by bad actors | Rate limiting, account caps, monitoring, manual ban. |

---

## 16. Constraints & Principles

### Hard Constraints

- Zero cost for all infrastructure in v1
- Single developer — scope decisions must respect this
- Privacy-first — user data not readable by developer or third parties

### Design Principles

- **Simplicity over features:** Every feature must earn its place
- **Mobile-first thinking:** If it's not easy on a phone, it's not done
- **User empathy:** Design every interaction for stressful review season
- **Ship early, iterate fast:** V1 minimal but complete
- **Transparency:** If AI doesn't have enough data, say so
- **Real product feel:** Every piece of UI text reads polished and human

---

## 17. Go-to-Market

- **Build in public:** Share journey on Twitter/X, LinkedIn
- **Launch posts:** Product Hunt, Indie Hackers, Hacker News, Reddit (r/productivity, r/sideproject, r/webdev)
- **Content marketing:** Write about performance review preparation, naturally reference MyLogMate
- **SEO:** Optimize for "work log app," "performance review preparation," "daily work journal"
- **Company pitch:** Lightweight, privacy-first alternative to internal tools

---

## 18. Open Questions (Resolved)

These were resolved during architecture design:

| Question | Resolution |
|----------|------------|
| LLM choice | Groq API free tier (Llama 3.1 8B). Modular adapter for Ollama swap. |
| Vector database | Qdrant Cloud (free 1GB). |
| Encryption strategy | AES-256 (Fernet) at application layer. Key in env var. |
| Hosting | Vercel (frontend) + Render (backend + worker). |
| AI query daily cap | 50/user/day. |
| Accent color | #93B5FF (light), #6B9FFF (dark). |
| Tech stack | React + FastAPI + PostgreSQL + Qdrant + Redis + Celery + LlamaIndex. |
