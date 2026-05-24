"""Context service — business logic for context CRUD.

Rules:
- Every query MUST filter by user_id. Data isolation is non-negotiable.
- The 'self' context cannot be deleted or renamed (enforced here, not just DB).
- Type is immutable after creation.
- Unique constraint (user_id, type, name) is enforced at DB level; we surface
  a ConflictError with a human-readable message on IntegrityError.
- Deleting a context cascades to log_entries at DB level (ON DELETE CASCADE).
  Embedding cleanup (Qdrant delete) is dispatched via Celery — see TODO Step 12.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.db.models.context import Context
from app.db.models.user import User
from app.schemas.contexts import (
    ContextResponse,
    CreateContextRequest,
    UpdateContextRequest,
)

logger = structlog.get_logger()


# ── Helpers ───────────────────────────────────────────────────────────────


async def _get_or_404(
    db: AsyncSession, context_id: uuid.UUID, user_id: uuid.UUID
) -> Context:
    """Return the context if it belongs to the user, else raise NotFoundError."""
    result = await db.execute(
        select(Context).where(Context.id == context_id, Context.user_id == user_id)
    )
    context: Context | None = result.scalar_one_or_none()
    if context is None:
        raise NotFoundError("Context")
    return context


# ── CRUD ──────────────────────────────────────────────────────────────────


async def list_contexts(db: AsyncSession, user: User) -> list[ContextResponse]:
    """Return all contexts for the user, ordered by type then name."""
    result = await db.execute(
        select(Context)
        .where(Context.user_id == user.id)
        .order_by(Context.type, Context.name)
    )
    contexts = result.scalars().all()
    return [ContextResponse.model_validate(c) for c in contexts]


async def get_context(
    db: AsyncSession, context_id: uuid.UUID, user: User
) -> ContextResponse:
    """Return a single context belonging to the user."""
    context = await _get_or_404(db, context_id, user.id)
    return ContextResponse.model_validate(context)


async def create_context(
    db: AsyncSession, user: User, body: CreateContextRequest
) -> ContextResponse:
    """Create a new context.

    Rules:
    - Users can create teammate or project contexts freely.
    - Creating a second 'self' context is rejected (unique constraint + explicit check).
    - Duplicate (type, name) per user is rejected.
    """
    if body.type == "self":
        raise ForbiddenError("The Self context is created automatically at signup")

    context = Context(user_id=user.id, type=body.type, name=body.name)
    db.add(context)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(
            f"A {body.type} context named '{body.name}' already exists"
        ) from exc

    await db.refresh(context)
    logger.info("context_created", context_id=str(context.id), type=body.type)
    return ContextResponse.model_validate(context)


async def update_context(
    db: AsyncSession,
    context_id: uuid.UUID,
    user: User,
    body: UpdateContextRequest,
) -> ContextResponse:
    """Rename a context.

    Rules:
    - The 'self' context cannot be renamed.
    - Name must remain unique within (user_id, type).
    """
    context = await _get_or_404(db, context_id, user.id)

    if context.type == "self":
        raise ForbiddenError("The Self context cannot be renamed")

    context.name = body.name

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(
            f"A {context.type} context named '{body.name}' already exists"
        ) from exc

    await db.refresh(context)
    logger.info("context_updated", context_id=str(context.id))
    return ContextResponse.model_validate(context)


async def delete_context(
    db: AsyncSession, context_id: uuid.UUID, user: User
) -> None:
    """Delete a context and all its log entries (via DB cascade).

    Rules:
    - The 'self' context cannot be deleted.
    - Embedding cleanup for the deleted log entries is dispatched via Celery.
      TODO Step 12: dispatch delete_context_embeddings.delay(str(context_id))
    """
    context = await _get_or_404(db, context_id, user.id)

    if context.type == "self":
        raise ForbiddenError("The Self context cannot be deleted")

    await db.delete(context)
    await db.commit()

    logger.info("context_deleted", context_id=str(context_id))
    # TODO Step 12: dispatch Celery task to purge Qdrant vectors for this context
