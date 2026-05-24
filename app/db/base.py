"""SQLAlchemy declarative base — all ORM models inherit from Base."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models.

    Alembic uses Base.metadata to autogenerate migrations.
    Import all models in app/db/models/__init__.py to ensure they're registered.
    """

    pass
