"""Tag routes — CRUD for user-scoped labels."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.tags import CreateTagRequest, TagResponse, UpdateTagRequest
from app.services import tags as tags_service

router = APIRouter(prefix="/tags", tags=["tags"])


# ── GET /tags ──────────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=ApiResponse[list[TagResponse]],
    summary="List all tags for the current user",
)
async def list_tags(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[TagResponse]]:
    tags = await tags_service.list_tags(db, current_user)
    return ApiResponse(data=tags, message="Tags retrieved")


# ── POST /tags ─────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=ApiResponse[TagResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new tag",
)
async def create_tag(
    body: CreateTagRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TagResponse]:
    tag = await tags_service.create_tag(db, current_user, body)
    return ApiResponse(data=tag, message="Tag created")


# ── GET /tags/{tag_id} ─────────────────────────────────────────────────────


@router.get(
    "/{tag_id}",
    response_model=ApiResponse[TagResponse],
    summary="Get a single tag by ID",
)
async def get_tag(
    tag_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TagResponse]:
    tag = await tags_service.get_tag(db, tag_id, current_user)
    return ApiResponse(data=tag, message="Tag retrieved")


# ── PATCH /tags/{tag_id} ───────────────────────────────────────────────────


@router.patch(
    "/{tag_id}",
    response_model=ApiResponse[TagResponse],
    summary="Rename a tag",
)
async def update_tag(
    tag_id: uuid.UUID,
    body: UpdateTagRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TagResponse]:
    tag = await tags_service.update_tag(db, tag_id, current_user, body)
    return ApiResponse(data=tag, message="Tag updated")


# ── DELETE /tags/{tag_id} ──────────────────────────────────────────────────


@router.delete(
    "/{tag_id}",
    response_model=ApiResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Delete a tag (log entries are not deleted)",
)
async def delete_tag(
    tag_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    await tags_service.delete_tag(db, tag_id, current_user)
    return ApiResponse(data=None, message="Tag deleted")
