Create a new API endpoint following MyLogMate conventions:

1. Route handler in app/api/v1/{domain}.py — thin, Depends for auth+db
2. Pydantic schemas in app/schemas/{domain}.py — request+response with validation
3. Service in app/services/{domain}_service.py — all business logic
4. If new table needed: SQLAlchemy model + Alembic migration
5. Register router in app/main.py
6. Write unit tests: happy path + 401 + 422
7. Run ruff check and mypy on new files

Endpoint needed: $ARGUMENTS
