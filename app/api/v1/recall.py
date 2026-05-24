"""Recall API v1 routes — AI-powered log recall and chat history.

Routes:
  POST   /recall               — run AI recall query
  GET    /recall/sessions      — list chat sessions (paginated)
  GET    /recall/sessions/{id} — get session with full message history
  DELETE /recall/sessions/{id} — delete a chat session
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, resolve_context_id
from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.models.user import User
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.recall import (
    ChatSessionDetailResponse,
    ChatSessionResponse,
    RecallQueryRequest,
    RecallQueryResponse,
)
from app.services import recall as recall_service

router = APIRouter(tags=["recall"])


@router.post(
    "/recall",
    response_model=ApiResponse[RecallQueryResponse],
    status_code=status.HTTP_200_OK,
)
@limiter.limit(f"{settings.AI_QUERY_DAILY_LIMIT}/day")
async def query_recall(
    request: Request,
    body: RecallQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[RecallQueryResponse]:
    """Run an AI recall query against the user's work logs.

    Requires: context_id (must be owned by the user, or "self" magic string).
    Optional: chat_session_id to continue an existing conversation.

    Rate limited to AI_QUERY_DAILY_LIMIT queries per day.
    """
    context_id = await resolve_context_id(body.context_id, current_user.id, db)
    result = await recall_service.recall_query(db, current_user, body, context_id)
    return ApiResponse(data=result, message="Query processed successfully")


@router.get(
    "/recall/sessions",
    response_model=PaginatedResponse[ChatSessionResponse],
    status_code=status.HTTP_200_OK,
)
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[ChatSessionResponse]:
    """Return paginated chat session list, newest first."""
    items, total = await recall_service.list_chat_sessions(
        db, current_user, page=page, page_size=page_size
    )
    return PaginatedResponse(
        data=items,
        total=total,
        page=page,
        page_size=page_size,
        message="Chat sessions retrieved",
    )


@router.get(
    "/recall/sessions/{session_id}",
    response_model=ApiResponse[ChatSessionDetailResponse],
    status_code=status.HTTP_200_OK,
)
async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ChatSessionDetailResponse]:
    """Return a single chat session with its full decrypted message history."""
    session = await recall_service.get_chat_session(db, current_user, session_id)
    return ApiResponse(data=session, message="Chat session retrieved")


@router.delete(
    "/recall/sessions/{session_id}",
    response_model=ApiResponse[None],
    status_code=status.HTTP_200_OK,
)
async def delete_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    """Delete a chat session and all its messages."""
    await recall_service.delete_chat_session(db, current_user, session_id)
    return ApiResponse(data=None, message="Chat session deleted")
