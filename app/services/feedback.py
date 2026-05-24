"""Feedback service — user-submitted feedback (plain text, not encrypted).

Feedback is voluntarily submitted by users. It is NOT encrypted because:
  - It is intended to be read by admins.
  - The user explicitly chose to share this content.
  - It does not contain log content or sensitive work data.
"""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.feedback import Feedback
from app.db.models.user import User
from app.schemas.feedback import CreateFeedbackRequest, FeedbackResponse

logger = structlog.get_logger()


async def submit_feedback(
    db: AsyncSession,
    user: User,
    body: CreateFeedbackRequest,
) -> FeedbackResponse:
    """Create a new feedback item for the current user.

    Feedback content is plain text — voluntarily submitted, admin-facing.
    """
    feedback = Feedback(
        user_id=user.id,
        content=body.content,
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)

    logger.info("feedback_submitted", user_id=str(user.id), feedback_id=str(feedback.id))
    return FeedbackResponse.model_validate(feedback)
