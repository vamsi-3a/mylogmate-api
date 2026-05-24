"""Template routes.

Sample templates (is_sample=True) are readable by all authenticated users
but cannot be modified via the API — they are seeded via `make seed`.

User templates (is_sample=False) are owned by the authenticated user and
support full CRUD.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.templates import (
    CreateTemplateRequest,
    TemplateResponse,
    UpdateTemplateRequest,
)
from app.services import templates as templates_service

router = APIRouter(prefix="/templates", tags=["templates"])


# ── GET /templates ─────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=ApiResponse[list[TemplateResponse]],
    summary="List all sample templates plus user's own templates",
)
async def list_templates(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[TemplateResponse]]:
    items = await templates_service.list_templates(db, current_user)
    return ApiResponse(data=items, message="Templates retrieved")


# ── POST /templates ────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=ApiResponse[TemplateResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a personal template",
)
async def create_template(
    body: CreateTemplateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TemplateResponse]:
    template = await templates_service.create_template(db, current_user, body)
    return ApiResponse(data=template, message="Template created")


# ── GET /templates/{template_id} ───────────────────────────────────────────


@router.get(
    "/{template_id}",
    response_model=ApiResponse[TemplateResponse],
    summary="Get a single template (sample or user-owned)",
)
async def get_template(
    template_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TemplateResponse]:
    template = await templates_service.get_template(db, template_id, current_user)
    return ApiResponse(data=template, message="Template retrieved")


# ── PATCH /templates/{template_id} ────────────────────────────────────────


@router.patch(
    "/{template_id}",
    response_model=ApiResponse[TemplateResponse],
    summary="Partially update a user-owned template",
)
async def update_template(
    template_id: uuid.UUID,
    body: UpdateTemplateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TemplateResponse]:
    template = await templates_service.update_template(
        db, template_id, current_user, body
    )
    return ApiResponse(data=template, message="Template updated")


# ── DELETE /templates/{template_id} ───────────────────────────────────────


@router.delete(
    "/{template_id}",
    response_model=ApiResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Delete a user-owned template",
)
async def delete_template(
    template_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    await templates_service.delete_template(db, template_id, current_user)
    return ApiResponse(data=None, message="Template deleted")
