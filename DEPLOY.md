# Deploying MyLogMate — Free Tier ($0/month)

End-to-end guide to take MyLogMate from code to a live, hosted app — backend +
frontend — entirely on free tiers. Follow the steps in order. Total time: ~45–60 min.

---

## 1. How it's hosted

```
                 ┌─────────────────────────┐
   Browser ────▶ │  Vercel (frontend SPA)  │   free
                 └───────────┬─────────────┘
                             │ HTTPS (VITE_API_URL)
                             ▼
                 ┌─────────────────────────┐
                 │ Render web service      │   free
                 │ FastAPI + embeddings +  │
                 │ emails (in-process)     │
                 └───┬─────────┬───────┬───┘
                     │         │       │
        ┌────────────▼──┐ ┌────▼────┐ ┌▼────────────┐
        │ Neon Postgres │ │ Qdrant  │ │ Redis Cloud │   all free
        │  (data)       │ │ (vectors)│ │ (idle*)     │
        └───────────────┘ └─────────┘ └─────────────┘
                     ▲
                     │ HTTPS
              ┌──────┴──────┐
              │  Groq API   │   free (LLM)
              └─────────────┘
```

There is **no separate Celery worker** — embedding and email tasks run inside the
API process (`CELERY_TASK_ALWAYS_EAGER=true`). That removes the only piece that
isn't free on Render.

\* Redis is only used by the `/ready` health check in this mode, but `REDIS_URL`
is still required by the app, so we provision a free Redis anyway.

### Cost & key limits

| Service | Tier | Notes |
|---|---|---|
| Vercel | Free | Static SPA, global CDN, auto-deploy on push |
| Render (web) | Free | **Sleeps after ~15 min idle → 30–50s cold start.** 512 MB RAM |
| Neon (Postgres) | Free | 0.5 GB. Auto-suspends after 5 min (wakes in ~1–2s) |
| Qdrant Cloud | Free | 1 GB cluster |
| Redis Cloud | Free | 30 MB |
| Groq | Free | ~30 req/min |

---

## 2. Accounts you'll need

Sign up (all free, GitHub login works for most):

- [GitHub](https://github.com) — code is at `vamsi-3a/mylogmate-api` and `vamsi-3a/mylogmate-web`
- [Render](https://render.com)
- [Vercel](https://vercel.com)
- [Neon](https://neon.tech)
- [Qdrant Cloud](https://cloud.qdrant.io)
- [Redis Cloud](https://redis.com/try-free/)
- [Groq](https://console.groq.com)
- *(optional)* Google Cloud Console (for "Sign in with Google") + a Gmail account (for password-reset emails)

---

## 3. Generate your encryption key (do this first)

The app encrypts all log content with a Fernet key. **Generate it once and save it
somewhere safe (a password manager). If you lose it, every stored log becomes
unreadable.** Render auto-generates `JWT_SECRET_KEY` for you, but this one you must create:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the output — this is your `ENCRYPTION_KEY`.

---

## 4. Provision the data services

Collect each credential into a scratch note; you'll paste them into Render in Step 6.

### 4a. Neon → `DATABASE_URL`
1. Create a project (any region; pick one close to you).
2. On the dashboard, copy the **connection string**. It looks like:
   `postgresql://user:pass@ep-xxx.aws.neon.tech/neondb?sslmode=require&channel_binding=require`
3. **Rewrite the query string** so the async driver accepts it — replace everything
   after `?` with `ssl=require`:
   ```
   postgresql://user:pass@ep-xxx.aws.neon.tech/neondb?ssl=require
   ```
   > ⚠️ This app uses the `asyncpg` driver, which rejects `sslmode=`. Use `ssl=require`.
   This single value is used for both runtime and migrations.

### 4b. Qdrant Cloud → `QDRANT_URL` + `QDRANT_API_KEY`
1. Create a **free cluster**.
2. Copy the cluster **URL** (e.g. `https://abc123.eu-central.aws.cloud.qdrant.io:6333`) → `QDRANT_URL`.
3. Create an **API key** → `QDRANT_API_KEY`.

### 4c. Redis Cloud → `REDIS_URL`
1. Create a free **30 MB** database.
2. Copy the public endpoint + password into a URL:
   `redis://default:YOUR_PASSWORD@redis-xxxxx.cloud.redislabs.com:port`

### 4d. Groq → `GROQ_API_KEY`
1. [console.groq.com](https://console.groq.com) → **API Keys** → create key (starts with `gsk_`).

---

## 5. Push the code to GitHub

The deploy config (`render.yaml`, `vercel.json`) is already committed. Just push both repos.

```bash
# Backend
cd mylogmate-api
git push origin main

# Frontend
cd ../mylogmate-web
git push origin main
```

> If `git push` reports the remote is behind/ahead, run `git pull --rebase origin main` first, resolve if needed, then push.

---

## 6. Deploy the backend on Render

1. Render Dashboard → **New +** → **Blueprint**.
2. Connect the **`vamsi-3a/mylogmate-api`** repo. Render reads `render.yaml` and proposes
   one free web service named **`mylogmate-api`**. Click **Apply**.
3. The first build downloads the embedding model — it takes a few minutes.
4. Open the **`mylogmate-api`** service → **Environment** tab → set these secrets
   (the ones marked "sync: false" in the blueprint):

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | your Neon string (with `?ssl=require`) |
   | `REDIS_URL` | your Redis Cloud URL |
   | `QDRANT_URL` | your Qdrant cluster URL |
   | `QDRANT_API_KEY` | your Qdrant API key |
   | `ENCRYPTION_KEY` | the Fernet key from Step 3 |
   | `GROQ_API_KEY` | your Groq key |
   | `CORS_ORIGINS` | *leave blank for now — set in Step 8* |
   | `FRONTEND_URL` | *leave blank for now — set in Step 8* |

   Optional (only if using those features):
   `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SMTP_USER`, `SMTP_PASSWORD`.

5. Click **Save, rebuild, and deploy**. On boot the service runs
   `alembic upgrade head` (creates all tables), then starts the API.
6. When it goes live, note the URL: **`https://mylogmate-api.onrender.com`**
   (Render shows the exact URL at the top of the service page).
7. Sanity check — open `https://mylogmate-api.onrender.com/health` → should return
   `{"status":"ok"}`. Then `/ready` → checks Postgres/Redis/Qdrant are all reachable.

---

## 7. Deploy the frontend on Vercel

1. Vercel → **Add New… → Project** → import **`vamsi-3a/mylogmate-web`**.
2. Framework Preset auto-detects **Vite** (config is in `vercel.json`). Leave build
   settings as-is.
3. **Environment Variables** → add:

   | Key | Value |
   |---|---|
   | `VITE_API_URL` | `https://mylogmate-api.onrender.com` (your Render URL from Step 6) |

   > `VITE_*` vars are baked in at build time, so this must be set **before** deploying.
4. Click **Deploy**. Note the URL: **`https://mylogmate-web.vercel.app`** (or your chosen domain).

---

## 8. Connect frontend ↔ backend

Now that you have the Vercel URL, finish wiring CORS and email links on the backend.

1. Render → `mylogmate-api` → **Environment** → set:

   | Key | Value |
   |---|---|
   | `CORS_ORIGINS` | `https://mylogmate-web.vercel.app` |
   | `FRONTEND_URL` | `https://mylogmate-web.vercel.app` |

   (Multiple origins: comma-separate them, e.g. `https://a.vercel.app,https://www.mydomain.com`.)
2. **Save** → Render redeploys automatically.

The refresh-token cookie is already configured for cross-site use
(`COOKIE_SAMESITE=none`, set in `render.yaml`), so login sessions persist across the
Vercel↔Render boundary.

---

## 9. (Optional) Google login & password-reset emails

**Google OAuth** — in Google Cloud Console → APIs & Services → Credentials → your
OAuth client:
- Authorized JavaScript origins: `https://mylogmate-web.vercel.app`
- Authorized redirect URIs: `https://mylogmate-web.vercel.app` (and your local `http://localhost:5173` for dev)
- Put the client ID/secret into `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` on Render.

**Gmail SMTP** (password reset) — create a Gmail
[App Password](https://myaccount.google.com/apppasswords) and set `SMTP_USER`
(your address) + `SMTP_PASSWORD` (the app password) on Render.

---

## 10. Smoke test (prove it works end-to-end)

Open `https://mylogmate-web.vercel.app` and:

1. **Sign up** with email + password. (First request may take ~30–50s if Render was asleep.)
2. **Create a log entry.** Saving waits briefly while the embedding is generated in-process — this is expected.
3. Go to **Recall** and **ask an AI question** about what you logged → confirms the
   full chain (Postgres → Qdrant → Groq) works.
4. Wait **16+ minutes**, then use the app again → you should still be logged in
   (confirms the cross-site refresh cookie works).

If all four pass, you're live. 🎉

---

## 11. Keep the free backend warm (recommended)

Render free services sleep after ~15 min idle, causing a 30–50s delay on the next
visit. To avoid this, add a free uptime pinger:

1. [UptimeRobot](https://uptimerobot.com) → **Add New Monitor**.
2. Type: **HTTP(s)**, URL: `https://mylogmate-api.onrender.com/health`, interval: **5 minutes**.

This keeps the instance awake within Render's free 750 hrs/month allowance.

---

## 12. Environment variable reference

Set on the **Render** service:

| Variable | Required | Source |
|---|---|---|
| `DATABASE_URL` | ✅ | Neon (use `?ssl=require`) |
| `REDIS_URL` | ✅ | Redis Cloud |
| `QDRANT_URL` | ✅ | Qdrant Cloud |
| `QDRANT_API_KEY` | ✅ | Qdrant Cloud |
| `ENCRYPTION_KEY` | ✅ | generated locally (Step 3) — **back up!** |
| `JWT_SECRET_KEY` | auto | Render generates it |
| `GROQ_API_KEY` | ✅ | Groq console |
| `CORS_ORIGINS` | ✅ | your Vercel URL |
| `FRONTEND_URL` | ✅ | your Vercel URL |
| `CELERY_TASK_ALWAYS_EAGER` | preset `true` | in `render.yaml` |
| `COOKIE_SAMESITE` | preset `none` | in `render.yaml` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | optional | Google Cloud Console |
| `SMTP_USER` / `SMTP_PASSWORD` | optional | Gmail App Password |

Set on **Vercel**:

| Variable | Required | Value |
|---|---|---|
| `VITE_API_URL` | ✅ | your Render API URL |

---

## 13. Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| First request hangs ~30–50s | Render cold start. Normal; add UptimeRobot (Step 11). |
| `sslmode is an invalid keyword argument` in Render logs | `DATABASE_URL` still has `?sslmode=require`. Change to `?ssl=require`. |
| Login works but you're logged out after ~15 min | `COOKIE_SAMESITE` not `none`, or `CORS_ORIGINS` doesn't exactly match the Vercel URL (scheme + host). |
| CORS error in browser console | `CORS_ORIGINS` on Render must equal the Vercel origin exactly, e.g. `https://mylogmate-web.vercel.app` (no trailing slash). |
| AI recall returns nothing | New logs need a moment to embed; also check `QDRANT_URL`/`QDRANT_API_KEY` and `GROQ_API_KEY`. |
| Service restarts / "out of memory" in logs | 512 MB is tight with the local model. Upgrade the Render service to Starter, or switch to Qdrant Cloud Inference (server-side embeddings) to drop the local model. |
| Migrations didn't run | They run on each start via the `dockerCommand`. Check the deploy logs for the `alembic upgrade head` output; verify `DATABASE_URL`. |

---

## 14. Upgrading later (when you outgrow free)

- **Remove cold starts:** set the Render service `plan: starter` ($7/mo) in `render.yaml`.
- **True background processing:** set `CELERY_TASK_ALWAYS_EAGER=false`, add a separate
  Render **Background Worker** (Starter, `Dockerfile.worker`) — the earlier two-service
  blueprint. This keeps the API snappy under load.
- **More RAM / lower latency:** migrate embeddings to **Qdrant Cloud Inference** so no
  model runs in your process.
