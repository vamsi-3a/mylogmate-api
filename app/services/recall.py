"""Recall service — business logic for AI-powered log recall.

Responsibilities:
  - Rate limiting: check + record AI query usage via AIQueryLog.
  - Chat session management: get existing or create new session.
  - Message persistence: encrypt + store user and assistant messages.
  - RAG orchestration: delegate to rag_pipeline.run_recall_query().
  - Return structured RecallQueryResponse.

Security invariants:
  - Chat message content is ALWAYS encrypted before DB write.
  - context_id MUST belong to the authenticated user.
  - Every DB query filters by user_id.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag_pipeline import run_recall_query
from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import decrypt_content, encrypt_content
from app.db.models.ai_query_log import AIQueryLog
from app.db.models.chat_message import ChatMessage
from app.db.models.chat_session import ChatSession
from app.db.models.context import Context
from app.db.models.user import User
from app.schemas.recall import (
    ChatMessageResponse,
    ChatSessionDetailResponse,
    ChatSessionResponse,
    RecallQueryRequest,
    RecallQueryResponse,
)

logger = structlog.get_logger()


# ── Helpers ───────────────────────────────────────────────────────────────


async def _assert_context_owned(
    db: AsyncSession, context_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Raise NotFoundError if the context doesn't belong to the user."""
    result = await db.execute(
        select(Context).where(
            Context.id == context_id,
            Context.user_id == user_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise NotFoundError("Context")


async def _count_queries_today(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Count AI queries used today (UTC) for rate limiting."""
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count()).select_from(AIQueryLog).where(
            AIQueryLog.user_id == user_id,
            AIQueryLog.created_at >= today_start,
        )
    )
    return result.scalar_one()


async def _get_or_create_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    context_id: uuid.UUID,
    chat_session_id: uuid.UUID | None,
    first_user_message: str,
) -> ChatSession:
    """Return the specified session or create a new one.

    If chat_session_id is provided, verifies it belongs to the user.
    A new session gets its title from the first 255 chars of the query.
    """
    if chat_session_id is not None:
        result = await db.execute(
            select(ChatSession).where(
                ChatSession.id == chat_session_id,
                ChatSession.user_id == user_id,
            )
        )
        session: ChatSession | None = result.scalar_one_or_none()
        if session is None:
            raise NotFoundError("Chat session")
        return session

    # Create new session — title from first 255 chars of user query
    session = ChatSession(
        user_id=user_id,
        context_id=context_id,
        title=first_user_message[:255],
    )
    db.add(session)
    await db.flush()  # populate session.id
    return session


def _message_to_response(
    message: ChatMessage,
    source_log_ids: list[uuid.UUID] | None = None,
) -> ChatMessageResponse:
    """Convert a ChatMessage ORM object to ChatMessageResponse (decrypted)."""
    return ChatMessageResponse(
        id=message.id,
        session_id=message.chat_session_id,
        role=message.role,
        content=decrypt_content(message.content_encrypted),
        source_log_ids=source_log_ids or [],
        created_at=message.created_at,
    )


# ── Recall query ──────────────────────────────────────────────────────────


async def recall_query(
    db: AsyncSession,
    user: User,
    body: RecallQueryRequest,
    context_id: uuid.UUID,
) -> RecallQueryResponse:
    """Process an AI recall query.

    Steps:
      1. Assert context ownership.
      2. Check daily rate limit (AI_QUERY_DAILY_LIMIT).
      3. Get or create chat session.
      4. Persist encrypted user message.
      5. Run RAG pipeline (embed → retrieve → LLM).
      6. Persist encrypted assistant message.
      7. Record AIQueryLog (rate limit audit).
      8. Return RecallQueryResponse.

    The context_id arg is the already-resolved UUID (route layer handles
    "self" magic strings via deps.resolve_context_id).

    Raises:
      NotFoundError: If context or chat session is not found.
      ValidationError: If daily rate limit is exceeded.
    """
    await _assert_context_owned(db, context_id, user.id)

    # ── Rate limit check ──────────────────────────────────────────────────
    queries_used = await _count_queries_today(db, user.id)
    daily_limit = settings.AI_QUERY_DAILY_LIMIT
    if queries_used >= daily_limit:
        raise ValidationError(
            f"Daily AI query limit of {daily_limit} reached. Try again tomorrow."
        )

    # ── Session ───────────────────────────────────────────────────────────
    session = await _get_or_create_session(
        db,
        user_id=user.id,
        context_id=context_id,
        chat_session_id=body.chat_session_id,
        first_user_message=body.query,
    )

    # ── Persist user message ──────────────────────────────────────────────
    user_msg = ChatMessage(
        chat_session_id=session.id,
        role="user",
        content_encrypted=encrypt_content(body.query),
    )
    db.add(user_msg)
    await db.flush()

    # ── Run RAG ───────────────────────────────────────────────────────────
    answer, source_ids, latency_ms = await run_recall_query(
        db=db,
        user_id=user.id,
        context_id=context_id,
        query=body.query,
    )

    # ── Persist assistant message ─────────────────────────────────────────
    assistant_msg = ChatMessage(
        chat_session_id=session.id,
        role="assistant",
        content_encrypted=encrypt_content(answer),
    )
    db.add(assistant_msg)

    # ── Audit log ─────────────────────────────────────────────────────────
    ai_log = AIQueryLog(
        user_id=user.id,
        context_id=context_id,
        prompt_preview=body.query[:150],  # NEVER the full query
        latency_ms=latency_ms,
    )
    db.add(ai_log)

    await db.commit()
    await db.refresh(user_msg)
    await db.refresh(assistant_msg)
    await db.refresh(session)

    logger.info(
        "recall_query_complete",
        user_id=str(user.id),
        session_id=str(session.id),
        latency_ms=latency_ms,
    )

    return RecallQueryResponse(
        answer=answer,
        source_log_ids=source_ids,
        latency_ms=latency_ms,
        chat_session_id=session.id,
    )


# ── Chat session history ──────────────────────────────────────────────────


async def list_chat_sessions(
    db: AsyncSession,
    user: User,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[ChatSessionResponse], int]:
    """Return paginated chat sessions for the user, newest first.

    Returns (items, total_count). Each session includes message_count.
    """
    count_result = await db.execute(
        select(func.count()).select_from(ChatSession).where(
            ChatSession.user_id == user.id
        )
    )
    total: int = count_result.scalar_one()

    offset = (page - 1) * page_size
    # Join with message count subquery
    msg_count_sq = (
        select(
            ChatMessage.chat_session_id.label("sid"),
            func.count().label("cnt"),
        )
        .group_by(ChatMessage.chat_session_id)
        .subquery()
    )

    result = await db.execute(
        select(ChatSession, func.coalesce(msg_count_sq.c.cnt, 0))
        .outerjoin(msg_count_sq, ChatSession.id == msg_count_sq.c.sid)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = result.all()

    items = [
        ChatSessionResponse(
            id=s.id,
            user_id=s.user_id,
            context_id=s.context_id if s.context_id is not None else s.id,
            title=s.title or "Untitled conversation",
            message_count=int(cnt),
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s, cnt in rows
    ]
    return items, total


async def get_chat_session(
    db: AsyncSession,
    user: User,
    session_id: uuid.UUID,
) -> ChatSessionDetailResponse:
    """Return a single chat session with its full message history (decrypted).

    Raises NotFoundError if session doesn't exist or doesn't belong to user.
    """
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user.id,
        )
    )
    session: ChatSession | None = result.scalar_one_or_none()
    if session is None:
        raise NotFoundError("Chat session")

    messages = [_message_to_response(m) for m in session.messages]

    return ChatSessionDetailResponse(
        id=session.id,
        user_id=session.user_id,
        context_id=session.context_id if session.context_id is not None else session.id,
        title=session.title or "Untitled conversation",
        message_count=len(messages),
        messages=messages,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


async def delete_chat_session(
    db: AsyncSession,
    user: User,
    session_id: uuid.UUID,
) -> None:
    """Hard-delete a chat session and all its messages (cascade).

    Raises NotFoundError if session doesn't exist or doesn't belong to user.
    """
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user.id,
        )
    )
    session: ChatSession | None = result.scalar_one_or_none()
    if session is None:
        raise NotFoundError("Chat session")

    await db.delete(session)
    await db.commit()
    logger.info("chat_session_deleted", session_id=str(session_id), user_id=str(user.id))
