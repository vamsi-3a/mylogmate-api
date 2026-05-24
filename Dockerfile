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

# Copy application source
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Non-root user for security
RUN useradd --no-create-home --shell /bin/false appuser
USER appuser

EXPOSE 8000

# NOTE: No embedding model pre-download needed — using Qdrant Cloud Inference.
# Qdrant generates embeddings server-side; we send raw text.

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
