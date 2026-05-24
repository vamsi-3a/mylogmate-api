"""Context routes — CRUD for user contexts (Self / Teammate / Project)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.contexts import (
    ContextResponse,
    CreateContextRequest,
    UpdateContextRequest,
)
from app.services import contexts as contexts_service

router = APIRouter(prefix="/contexts", tags=["contexts"])


# ── GET /contexts ──────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=ApiResponse[list[ContextResponse]],
    summary="List all contexts for the current user",
)
async def list_contexts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[ContextResponse]]:
    contexts = await contexts_service.list_contexts(db, current_user)
    return ApiResponse(data=contexts, message="Contexts retrieved")


# ── POST /contexts ─────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=ApiResponse[ContextResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new teammate or project context",
)
async def create_context(
    body: CreateContextRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ContextResponse]:
    context = await contexts_service.create_context(db, current_user, body)
    return ApiResponse(data=context, message="Context created")


# ── GET /contexts/{context_id} ─────────────────────────────────────────────


@router.get(
    "/{context_id}",
    response_model=ApiResponse[ContextResponse],
    summary="Get a single context by ID",
)
async def get_context(
    context_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ContextResponse]:
    context = await contexts_service.get_context(db, context_id, current_user)
    return ApiResponse(data=context, message="Context retrieved")


# ── PATCH /contexts/{context_id} ───────────────────────────────────────────


@router.patch(
    "/{context_id}",
    response_model=ApiResponse[ContextResponse],
    summary="Rename a context (teammate or project only)",
)
async def update_context(
    context_id: uuid.UUID,
    body: UpdateContextRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ContextResponse]:
    context = await contexts_service.update_context(db, context_id, current_user, body)
    return ApiResponse(data=context, message="Context updated")


# ── DELETE /contexts/{context_id} ──────────────────────────────────────────


@router.delete(
    "/{context_id}",
    response_model=ApiResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Delete a context and all its log entries",
)
async def delete_context(
    context_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    await contexts_service.delete_context(db, context_id, current_user)
    return ApiResponse(data=None, message="Context deleted")
