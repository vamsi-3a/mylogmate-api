"""Template service — business logic for template CRUD.

Two template kinds coexist:
- Sample templates (is_sample=True, user_id=None): seeded at startup, readable by
  all authenticated users, immutable via API.
- User templates (is_sample=False, user_id=<uuid>): owned by individual users.

Security invariants:
- List/Get: sample OR owned by current user.
- Create/Update/Delete: only user-owned templates; sample templates are read-only.
- No cross-user access to personal templates.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.db.models.template import Template
from app.db.models.user import User
from app.schemas.templates import (
    CreateTemplateRequest,
    TemplateResponse,
    UpdateTemplateRequest,
)

logger = structlog.get_logger()


# ── Internal helpers ──────────────────────────────────────────────────────


def _to_response(template: Template) -> TemplateResponse:
    return TemplateResponse.model_validate(template)


async def _get_readable_or_404(
    db: AsyncSession, template_id: uuid.UUID, user_id: uuid.UUID
) -> Template:
    """Return a template that the user can read (sample or owned)."""
    result = await db.execute(
        select(Template).where(
            Template.id == template_id,
            or_(
                Template.user_id == user_id,
                Template.is_sample.is_(True),
            ),
        )
    )
    template: Template | None = result.scalar_one_or_none()
    if template is None:
        raise NotFoundError("Template")
    return template


async def _get_owned_or_404(
    db: AsyncSession, template_id: uuid.UUID, user_id: uuid.UUID
) -> Template:
    """Return a user-owned (non-sample) template, else raise 404 or 403."""
    result = await db.execute(
        select(Template).where(
            Template.id == template_id,
        )
    )
    template: Template | None = result.scalar_one_or_none()
    if template is None:
        raise NotFoundError("Template")
    if template.is_sample:
        raise ForbiddenError("Sample templates cannot be modified")
    if template.user_id != user_id:
        raise NotFoundError("Template")
    return template


# ── CRUD ──────────────────────────────────────────────────────────────────


async def list_templates(
    db: AsyncSession, user: User
) -> list[TemplateResponse]:
    """Return all sample templates plus the user's own templates.

    Ordered alphabetically by name.
    """
    result = await db.execute(
        select(Template)
        .where(
            or_(
                Template.user_id == user.id,
                Template.is_sample.is_(True),
            )
        )
        .order_by(Template.is_sample.desc(), Template.name)
    )
    templates = result.scalars().all()
    return [_to_response(t) for t in templates]


async def get_template(
    db: AsyncSession, template_id: uuid.UUID, user: User
) -> TemplateResponse:
    """Return a single template (sample or owned)."""
    template = await _get_readable_or_404(db, template_id, user.id)
    return _to_response(template)


async def create_template(
    db: AsyncSession, user: User, body: CreateTemplateRequest
) -> TemplateResponse:
    """Create a personal template for the user.

    Raises ConflictError if a template with the same name already exists for this user.
    """
    template = Template(
        user_id=user.id,
        name=body.name,
        content=body.content,
        is_sample=False,
        category=None,
    )
    db.add(template)
    try:
        await db.commit()
        await db.refresh(template)
    except IntegrityError:
        await db.rollback()
        raise ConflictError(f"Template named '{body.name}' already exists") from None

    logger.info("template_created", template_id=str(template.id))
    return _to_response(template)


async def update_template(
    db: AsyncSession,
    template_id: uuid.UUID,
    user: User,
    body: UpdateTemplateRequest,
) -> TemplateResponse:
    """Partially update a user-owned template.

    Raises ForbiddenError for sample templates.
    Raises ConflictError on duplicate name.
    """
    template = await _get_owned_or_404(db, template_id, user.id)

    if body.name is not None:
        template.name = body.name
    if body.content is not None:
        template.content = body.content

    try:
        await db.commit()
        await db.refresh(template)
    except IntegrityError:
        await db.rollback()
        name = body.name or template.name
        raise ConflictError(f"Template named '{name}' already exists") from None

    logger.info("template_updated", template_id=str(template_id))
    return _to_response(template)


async def delete_template(
    db: AsyncSession, template_id: uuid.UUID, user: User
) -> None:
    """Delete a user-owned template.

    Raises ForbiddenError for sample templates.
    """
    template = await _get_owned_or_404(db, template_id, user.id)
    await db.delete(template)
    await db.commit()
    logger.info("template_deleted", template_id=str(template_id))
