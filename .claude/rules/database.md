---
path: app/db/**
---
- UUID PKs: Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
- Timestamps: DateTime(timezone=True) with UTC defaults
- Never raw SQL string concatenation. SQLAlchemy parameterized queries only.
- Every model change → Alembic migration. No manual ALTER TABLE.
- content_encrypted: NEVER plain text. Encrypt via app/core/security.py.
- Import all models in app/db/models/__init__.py for Alembic autogenerate.
