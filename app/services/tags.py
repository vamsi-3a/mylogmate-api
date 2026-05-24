"""Tag service — business logic for tag CRUD.

Rules:
- Every query MUST filter by user_id. Data isolation is non-negotiable.
- (user_id, name) is unique — UniqueConstraint on the tags table.
- Deleting a tag removes it from all log_entry_tags rows (ON DELETE CASCADE at DB).
  The log entries themselves are NOT deleted.
- Tag name comparison is case-sensitive (matches DB collation).
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.log_entry_tag import log_entry_tags
from app.db.models.tag import Tag
from app.db.models.user import User
from app.schemas.tags import CreateTagRequest, TagResponse, UpdateTagRequest

logger = structlog.get_logger()


# ── Helpers ───────────────────────────────────────────────────────────────


async def _get_or_404(
    db: AsyncSession, tag_id: uuid.UUID, user_id: uuid.UUID
) -> Tag:
    """Return the tag if it belongs to the user, else raise NotFoundError."""
    result = await db.execute(
        select(Tag).where(Tag.id == tag_id, Tag.user_id == user_id)
    )
    tag: Tag | None = result.scalar_one_or_none()
    if tag is None:
        raise NotFoundError("Tag")
    return tag


# ── CRUD ──────────────────────────────────────────────────────────────────


async def list_tags(db: AsyncSession, user: User) -> list[TagResponse]:
    """Return all tags for the user, ordered alphabetically, with use counts."""
    use_count_sq = (
        select(
            log_entry_tags.c.tag_id.label("tid"),
            func.count().label("cnt"),
        )
        .group_by(log_entry_tags.c.tag_id)
        .subquery()
    )
    result = await db.execute(
        select(Tag, func.coalesce(use_count_sq.c.cnt, 0))
        .outerjoin(use_count_sq, Tag.id == use_count_sq.c.tid)
        .where(Tag.user_id == user.id)
        .order_by(Tag.name)
    )
    return [
        TagResponse(
            id=tag.id,
            user_id=tag.user_id,
            name=tag.name,
            use_count=int(cnt),
            created_at=tag.created_at,
            updated_at=tag.updated_at,
        )
        for tag, cnt in result.all()
    ]


async def get_tag(
    db: AsyncSession, tag_id: uuid.UUID, user: User
) -> TagResponse:
    """Return a single tag belonging to the user."""
    tag = await _get_or_404(db, tag_id, user.id)
    return TagResponse.model_validate(tag)


async def create_tag(
    db: AsyncSession, user: User, body: CreateTagRequest
) -> TagResponse:
    """Create a new tag.

    Raises ConflictError if a tag with the same name already exists for the user.
    """
    tag = Tag(user_id=user.id, name=body.name)
    db.add(tag)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(f"Tag named '{body.name}' already exists") from exc

    await db.refresh(tag)
    logger.info("tag_created", tag_id=str(tag.id))
    return TagResponse.model_validate(tag)


async def update_tag(
    db: AsyncSession,
    tag_id: uuid.UUID,
    user: User,
    body: UpdateTagRequest,
) -> TagResponse:
    """Rename a tag.

    Raises NotFoundError if tag doesn't belong to user.
    Raises ConflictError if new name collides with an existing tag.
    """
    tag = await _get_or_404(db, tag_id, user.id)
    tag.name = body.name

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(f"Tag named '{body.name}' already exists") from exc

    await db.refresh(tag)
    logger.info("tag_updated", tag_id=str(tag.id))
    return TagResponse.model_validate(tag)


async def delete_tag(
    db: AsyncSession, tag_id: uuid.UUID, user: User
) -> None:
    """Delete a tag. Log entries that used this tag are NOT deleted.

    The log_entry_tags rows are removed via ON DELETE CASCADE on tag_id FK.
    """
    tag = await _get_or_404(db, tag_id, user.id)
    await db.delete(tag)
    await db.commit()
    logger.info("tag_deleted", tag_id=str(tag_id))
