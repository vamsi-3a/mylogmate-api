.PHONY: dev build test lint format migrate migration seed shell clean help

# ── Local dev ──────────────────────────────────────────────────────────────
dev:
	docker-compose up

dev-build:
	docker-compose up --build

down:
	docker-compose down

# ── Code quality ───────────────────────────────────────────────────────────
lint:
	ruff check app/ tests/
	mypy app/

format:
	ruff format app/ tests/
	ruff check --fix app/ tests/

# ── Tests ──────────────────────────────────────────────────────────────────
test:
	pytest -v --tb=short

test-cov:
	pytest -v --cov=app --cov-report=html --cov-report=term-missing

# ── Database ───────────────────────────────────────────────────────────────
migrate:
	alembic upgrade head

# Usage: make migration msg="add user table"
migration:
	alembic revision --autogenerate -m "$(msg)"

downgrade:
	alembic downgrade -1

migrate-history:
	alembic history --verbose

# ── Seed data ──────────────────────────────────────────────────────────────
seed:
	python -m app.db.seed

# ── Dev utilities ──────────────────────────────────────────────────────────
shell:
	python -c "import asyncio; from app.core.config import settings; print('Settings loaded:', settings.APP_ENV)"

gen-key:
	@python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

gen-secret:
	@python -c "import secrets; print(secrets.token_hex(32))"

# ── Docker ─────────────────────────────────────────────────────────────────
build:
	docker build -t mylogmate-api .

build-worker:
	docker build -f Dockerfile.worker -t mylogmate-worker .

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage

# ── Help ───────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "MyLogMate API — Development Commands"
	@echo "======================================"
	@echo "  make dev          Start all services (docker-compose up)"
	@echo "  make test         Run pytest"
	@echo "  make lint         Run ruff + mypy"
	@echo "  make format       Auto-format with ruff"
	@echo "  make migrate      Apply Alembic migrations (alembic upgrade head)"
	@echo "  make migration    Generate new migration (msg='your message')"
	@echo "  make seed         Seed sample templates + admin user"
	@echo "  make gen-key      Generate a Fernet encryption key"
	@echo "  make gen-secret   Generate a JWT secret key"
	@echo "  make clean        Remove build artifacts"
	@echo ""
