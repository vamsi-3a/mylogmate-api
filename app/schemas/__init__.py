"""Pydantic schemas — request and response models for all API endpoints."""

from app.schemas.admin import (
    AdminStatsResponse,
    DailyCount,
    FeedbackAdminResponse,
    UserAdminResponse,
)
from app.schemas.auth import (
    ForgotPasswordRequest,
    GoogleAuthRequest,
    LoginRequest,
    ResetPasswordRequest,
    SignupRequest,
    TokenResponse,
    UpdatePasswordRequest,
    UpdateProfileRequest,
    UserResponse,
)
from app.schemas.common import (
    ApiResponse,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    PaginatedResponse,
    ReadyResponse,
    ServiceStatus,
)
from app.schemas.contexts import (
    ContextResponse,
    CreateContextRequest,
    UpdateContextRequest,
)
from app.schemas.feedback import CreateFeedbackRequest, FeedbackResponse
from app.schemas.logs import (
    AssignTagsRequest,
    CalendarDayResponse,
    CalendarMonthResponse,
    CreateLogRequest,
    LogResponse,
    UpdateLogRequest,
)
from app.schemas.recall import (
    ChatMessageResponse,
    ChatSessionDetailResponse,
    ChatSessionResponse,
    RecallQueryRequest,
    RecallQueryResponse,
)
from app.schemas.tags import CreateTagRequest, TagResponse, UpdateTagRequest
from app.schemas.templates import (
    CreateTemplateRequest,
    TemplateResponse,
    UpdateTemplateRequest,
)

__all__ = [
    # admin
    "AdminStatsResponse",
    "DailyCount",
    "FeedbackAdminResponse",
    "UserAdminResponse",
    # auth
    "ForgotPasswordRequest",
    "GoogleAuthRequest",
    "LoginRequest",
    "ResetPasswordRequest",
    "SignupRequest",
    "TokenResponse",
    "UpdatePasswordRequest",
    "UpdateProfileRequest",
    "UserResponse",
    # common
    "ApiResponse",
    "ErrorDetail",
    "ErrorResponse",
    "HealthResponse",
    "PaginatedResponse",
    "ReadyResponse",
    "ServiceStatus",
    # contexts
    "ContextResponse",
    "CreateContextRequest",
    "UpdateContextRequest",
    # feedback
    "CreateFeedbackRequest",
    "FeedbackResponse",
    # logs
    "AssignTagsRequest",
    "CalendarDayResponse",
    "CalendarMonthResponse",
    "CreateLogRequest",
    "LogResponse",
    "UpdateLogRequest",
    # recall
    "ChatMessageResponse",
    "ChatSessionDetailResponse",
    "ChatSessionResponse",
    "RecallQueryRequest",
    "RecallQueryResponse",
    # tags
    "CreateTagRequest",
    "TagResponse",
    "UpdateTagRequest",
    # templates
    "CreateTemplateRequest",
    "TemplateResponse",
    "UpdateTemplateRequest",
]
