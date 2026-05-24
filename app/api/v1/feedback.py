"""Feedback API v1 routes.

Routes:
  POST /feedback — submit user feedback
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.feedback import CreateFeedbackRequest, FeedbackResponse
from app.services import feedback as feedback_service

router = APIRouter(tags=["feedback"])


@router.post(
    "/feedback",
    response_model=ApiResponse[FeedbackResponse],
    status_code=status.HTTP_201_CREATED,
)
async def submit_feedback(
    body: CreateFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[FeedbackResponse]:
    """Submit in-app feedback. Content is plain text (not encrypted).

    Feedback is stored and surfaced in the admin dashboard.
    """
    result = await feedback_service.submit_feedback(db, current_user, body)
    return ApiResponse(data=result, message="Feedback submitted. Thank you!")
