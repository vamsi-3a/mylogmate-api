"""ORM model registry — import ALL models here.

This module is imported by alembic/env.py so that every model's table
is registered with Base.metadata before autogenerate runs.

Import order respects FK dependencies (parents before children),
though SQLAlchemy resolves string-based FKs lazily so the order is
mainly for human readability.
"""

from app.db.models.ai_query_log import AIQueryLog
from app.db.models.chat_message import ChatMessage
from app.db.models.chat_session import ChatSession
from app.db.models.context import Context
from app.db.models.feedback import Feedback
from app.db.models.log_entry import LogEntry
from app.db.models.log_entry_tag import log_entry_tags  # association table
from app.db.models.tag import Tag
from app.db.models.template import Template
from app.db.models.user import User

__all__ = [
    "User",
    "Context",
    "log_entry_tags",
    "Tag",
    "LogEntry",
    "Template",
    "ChatSession",
    "ChatMessage",
    "Feedback",
    "AIQueryLog",
]
