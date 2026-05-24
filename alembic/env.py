"""Alembic migration environment — async SQLAlchemy 2.0 configuration.

Reads database URL from app settings (not alembic.ini) so there's one source of truth.
Imports all models via app.db.models so autogenerate detects schema changes.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ── Load app settings + models ────────────────────────────────────────────

from app.core.config import settings
from app.db.base import Base

# Import all models so their tables appear in Base.metadata for autogenerate.
# Add each model import here as they are created in Step 3.
import app.db.models  # noqa: F401 — registers all models with Base.metadata

# ── Alembic config ────────────────────────────────────────────────────────

config = context.config

# Override sqlalchemy.url from app settings (ignores the value in alembic.ini)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# ── Offline migrations (generates SQL without a live DB) ──────────────────


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — generates SQL script without connecting."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,         # Detect column type changes
        compare_server_default=True,  # Detect default value changes
    )

    with context.begin_transaction():
        context.run_migrations()


# ── Online migrations (connects to DB and applies changes) ─────────────────


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create async engine and run migrations via sync connection wrapper."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # Don't pool connections during migrations
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migration mode."""
    asyncio.run(run_async_migrations())


# ── Entry point ────────────────────────────────────────────────────────────

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
