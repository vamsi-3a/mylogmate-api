# ── Build stage ───────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# ── Runtime stage ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Runtime system deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Pre-download embedding model so first request is fast (no cold-start download)
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"

# Copy application source
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Non-root user for security
RUN useradd --no-create-home --shell /bin/false appuser && \
    chown -R appuser /tmp /root/.cache 2>/dev/null || true
USER appuser

EXPOSE 8000

# Run DB migrations, then serve. exec-form CMD is passed verbatim by Docker
# (no host re-parsing), so the && and quoting work reliably on any platform.
# `exec` hands PID 1 to uvicorn so it receives SIGTERM for graceful shutdown.
# --workers 1 keeps a single embedding-model instance in memory (512 MB free tier).
# (docker-compose overrides this command for local dev; the worker uses Dockerfile.worker.)
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"]
