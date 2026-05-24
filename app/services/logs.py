"""Log entry service — business logic for log CRUD.

Security invariants (non-negotiable):
- Every query filters by user_id AND context_id.
- content is ALWAYS encrypted before DB write, decrypted after read.
- content_encrypted is NEVER returned in a response.

Lifecycle:
  Create → encrypt content → embedding_status='pending' → TODO Step 12: dispatch embed task
  Update → re-encrypt content → embedding_status='pending' → TODO Step 12: re-embed
  Delete → is_deleted=True (soft) → TODO Step 12: dispatch delete_embedding task
"""

from __future__ import annotations

import uuid
from datetime import date

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import decrypt_content, encrypt_content
from app.db.models.context import Context
from app.db.models.log_entry import LogEntry
from app.db.models.log_entry_tag import log_entry_tags
from app.db.models.tag import Tag
from app.db.models.user import User
from app.schemas.logs import (
    AssignTagsRequest,
    CreateLogRequest,
    LogResponse,
    UpdateLogRequest,
)
from app.schemas.tags import TagResponse

logger = structlog.get_logger()


# ── Internal helpers ──────────────────────────────────────────────────────


def _to_response(entry: LogEntry) -> LogResponse:
    """Build LogResponse from a LogEntry, decrypting content.

    We cannot use model_validate() directly because the ORM field is
    content_encrypted but the schema field is content (decrypted).
    """
    return LogResponse(
        id=entry.id,
        context_id=entry.context_id,
        content=decrypt_content(entry.content_encrypted),
        date_type=entry.date_type,
        date_start=entry.date_start,
        date_end=entry.date_end,
        embedding_status=entry.embedding_status,
        tags=[TagResponse.model_validate(t) for t in entry.tags],
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


async def _get_or_404(
    db: AsyncSession, log_id: uuid.UUID, user_id: uuid.UUID
) -> LogEntry:
    """Return a non-deleted log entry belonging to the user, else 404."""
    result = await db.execute(
        select(LogEntry).where(
            LogEntry.id == log_id,
            LogEntry.user_id == user_id,
            LogEntry.is_deleted.is_(False),
        )
    )
    entry: LogEntry | None = result.scalar_one_or_none()
    if entry is None:
        raise NotFoundError("Log entry")
    return entry


async def _assert_context_owned(
    db: AsyncSession, context_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Raise ForbiddenError if the context doesn't belong to the user."""
    result = await db.execute(
        select(Context).where(
            Context.id == context_id,
            Context.user_id == user_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise NotFoundError("Context")


async def _resolve_tags(
    db: AsyncSession, tag_ids: list[uuid.UUID], user_id: uuid.UUID
) -> list[Tag]:
    """Load Tag objects, validating they all belong to the user.

    Raises ValidationError if any tag_id is not found for this user.
    """
    if not tag_ids:
        return []

    result = await db.execute(
        select(Tag).where(Tag.id.in_(tag_ids), Tag.user_id == user_id)
    )
    tags = list(result.scalars().all())

    if len(tags) != len(tag_ids):
        raise ValidationError("One or more tag IDs are invalid or don't belong to you")

    return tags


# ── CRUD ──────────────────────────────────────────────────────────────────


async def list_logs(
    db: AsyncSession,
    user: User,
    context_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
    date_start: date | None = None,
    date_end: date | None = None,
    tag_ids: list[uuid.UUID] | None = None,
) -> tuple[list[LogResponse], int]:
    """Return paginated log entries for a context.

    Returns (items, total_count).
    Entries are ordered newest first (by date_start DESC, created_at DESC).
    """
    await _assert_context_owned(db, context_id, user.id)

    # ── Base filter ──────────────────────────────────────────────────────
    filters = [
        LogEntry.user_id == user.id,
        LogEntry.context_id == context_id,
        LogEntry.is_deleted.is_(False),
    ]

    if date_start:
        filters.append(LogEntry.date_start >= date_start)
    if date_end:
        filters.append(LogEntry.date_end <= date_end)

    if tag_ids:
        # Only entries that have ALL the requested tags (AND semantics)
        for tid in tag_ids:
            filters.append(
                LogEntry.id.in_(
                    select(log_entry_tags.c.log_entry_id).where(
                        log_entry_tags.c.tag_id == tid
                    )
                )
            )

    where_clause = and_(*filters)

    # ── Total count ──────────────────────────────────────────────────────
    count_result = await db.execute(
        select(func.count()).select_from(LogEntry).where(where_clause)
    )
    total: int = count_result.scalar_one()

    # ── Paginated fetch ──────────────────────────────────────────────────
    offset = (page - 1) * page_size
    result = await db.execute(
        select(LogEntry)
        .where(where_clause)
        .order_by(LogEntry.date_start.desc(), LogEntry.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    entries = result.scalars().all()
    return [_to_response(e) for e in entries], total


async def get_log(
    db: AsyncSession, log_id: uuid.UUID, user: User
) -> LogResponse:
    """Return a single log entry (decrypted)."""
    entry = await _get_or_404(db, log_id, user.id)
    return _to_response(entry)


async def create_log(
    db: AsyncSession, user: User, body: CreateLogRequest
) -> LogResponse:
    """Create a log entry.

    - Validates context ownership.
    - Validates tag ownership.
    - Encrypts content before storing.
    - Sets embedding_status='pending'.
    - TODO Step 12: dispatch embed_log_entry.delay(str(entry.id))
    """
    await _assert_context_owned(db, body.context_id, user.id)
    tags = await _resolve_tags(db, body.tag_ids, user.id)

    entry = LogEntry(
        user_id=user.id,
        context_id=body.context_id,
        content_encrypted=encrypt_content(body.content),
        date_type=body.date_type,
        date_start=body.date_start,
        date_end=body.date_end,
        embedding_status="pending",
        tags=tags,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    logger.info("log_created", log_id=str(entry.id), context_id=str(body.context_id))
    # TODO Step 12: dispatch embed_log_entry.delay(str(entry.id))
    return _to_response(entry)


async def update_log(
    db: AsyncSession,
    log_id: uuid.UUID,
    user: User,
    body: UpdateLogRequest,
) -> LogResponse:
    """Partially update a log entry.

    - content changes trigger re-encryption and embedding_status reset to 'pending'.
    - tag_ids replaces the full tag set (if provided).
    - TODO Step 12: if content changed, dispatch re_embed_log_entry.delay(str(entry.id))
    """
    entry = await _get_or_404(db, log_id, user.id)
    content_changed = False

    if body.content is not None:
        entry.content_encrypted = encrypt_content(body.content)
        entry.embedding_status = "pending"
        content_changed = True

    if body.date_type is not None:
        entry.date_type = body.date_type

    if body.date_start is not None:
        entry.date_start = body.date_start

    if body.date_end is not None:
        entry.date_end = body.date_end

    # Cross-field validation after partial update
    if entry.date_end < entry.date_start:
        raise ValidationError("date_end must be >= date_start")

    if body.tag_ids is not None:
        entry.tags = await _resolve_tags(db, body.tag_ids, user.id)

    await db.commit()
    await db.refresh(entry)

    logger.info("log_updated", log_id=str(log_id), content_changed=content_changed)
    # TODO Step 12: if content_changed: dispatch re_embed_log_entry.delay(str(entry.id))
    return _to_response(entry)


async def delete_log(
    db: AsyncSession, log_id: uuid.UUID, user: User
) -> None:
    """Soft-delete a log entry (sets is_deleted=True).

    The DB row is retained for data-recovery purposes. The Qdrant vector
    is removed asynchronously by a Celery task.
    TODO Step 12: dispatch delete_log_embedding.delay(str(log_id))
    """
    entry = await _get_or_404(db, log_id, user.id)
    entry.is_deleted = True
    await db.commit()

    logger.info("log_deleted", log_id=str(log_id))
    # TODO Step 12: dispatch delete_log_embedding.delay(str(log_id))


async def assign_tags(
    db: AsyncSession,
    log_id: uuid.UUID,
    user: User,
    body: AssignTagsRequest,
) -> LogResponse:
    """Replace the full set of tags on a log entry.

    Raises NotFoundError if the entry doesn't exist.
    Raises ValidationError if any tag doesn't belong to the user.
    """
    entry = await _get_or_404(db, log_id, user.id)
    entry.tags = await _resolve_tags(db, body.tag_ids, user.id)

    await db.commit()
    await db.refresh(entry)

    logger.info("log_tags_assigned", log_id=str(log_id), tag_count=len(body.tag_ids))
    return _to_response(entry)
