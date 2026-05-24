"""Async SQLAlchemy engine and session factory.

Usage in routes/services (via dep injection):
    async with AsyncSessionLocal() as session:
        ...

For Celery tasks (sync), use a separate sync engine (added in Step 12).
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# Create the async engine — connection pool is lazy (connects on first use)
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # Log SQL queries only in debug mode
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,   # Detect stale connections before use
    pool_recycle=3600,    # Recycle connections every hour
)

# Session factory — use via async context manager
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Allow accessing attributes after commit
    autoflush=False,
    autocommit=False,
)
