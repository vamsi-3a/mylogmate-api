"""Celery task unit tests.

All external calls (DB, Qdrant, SMTP, generate_embedding) are mocked.

Strategy:
  Direct task calls (task(args)) don't set up a full Celery request context, so
  we test the business logic directly by calling the task function and patching
  `task.retry` to raise Retry, letting us verify retry is triggered on failure.

Coverage:
- embed_log_entry
  — happy path: load → decrypt → embed → upsert → status='embedded'
  — log entry not found: skips silently (no upsert, no status update)
  — embedding failure: task.retry() is called
  — max-retries: embedding_status set to 'failed' after all retries exhausted
- delete_log_embedding
  — happy path: delete vector
  — failure: task.retry() is called
- send_reset_password_email
  — happy path: SMTP send
  — SMTP not configured: skips silently
  — SMTP error: task.retry() is called
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from celery.exceptions import MaxRetriesExceededError, Retry

# ── Helpers ───────────────────────────────────────────────────────────────


def _make_log_entry(log_id: uuid.UUID | None = None) -> MagicMock:
    entry = MagicMock()
    entry.id = log_id or uuid.uuid4()
    entry.user_id = uuid.uuid4()
    entry.context_id = uuid.uuid4()
    entry.content_encrypted = "encrypted-content-str"
    entry.date_start = MagicMock()
    entry.date_start.isoformat.return_value = "2026-05-01"
    entry.date_end = MagicMock()
    entry.date_end.isoformat.return_value = "2026-05-01"
    return entry


# ── embed_log_entry ───────────────────────────────────────────────────────


def test_embed_log_entry_success() -> None:
    """Happy path: loads entry, generates embedding, upserts, marks embedded."""
    from app.workers.embedding_tasks import embed_log_entry

    log_id = uuid.uuid4()
    entry = _make_log_entry(log_id)
    vector = [0.1] * 384

    with (
        patch(
            "app.workers.embedding_tasks._load_log_entry",
            new=AsyncMock(return_value=entry),
        ),
        patch(
            "app.workers.embedding_tasks.decrypt_content",
            return_value="Some log content",
        ),
        patch(
            "app.workers.embedding_tasks.generate_embedding",
            return_value=vector,
        ),
        patch(
            "app.workers.embedding_tasks.upsert_log_vector",
            new=AsyncMock(),
        ) as mock_upsert,
        patch(
            "app.workers.embedding_tasks._set_embedding_status",
            new=AsyncMock(),
        ) as mock_status,
    ):
        embed_log_entry(str(log_id))

    mock_upsert.assert_called_once()
    mock_status.assert_called_once_with(log_id, "embedded")


def test_embed_log_entry_not_found() -> None:
    """Skips silently when log entry is not found."""
    from app.workers.embedding_tasks import embed_log_entry

    with (
        patch(
            "app.workers.embedding_tasks._load_log_entry",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.workers.embedding_tasks.upsert_log_vector",
            new=AsyncMock(),
        ) as mock_upsert,
        patch(
            "app.workers.embedding_tasks._set_embedding_status",
            new=AsyncMock(),
        ) as mock_status,
    ):
        embed_log_entry(str(uuid.uuid4()))

    mock_upsert.assert_not_called()
    mock_status.assert_not_called()


def test_embed_log_entry_retries_on_failure() -> None:
    """Calls task.retry() when embedding generation raises an exception."""
    from app.workers.embedding_tasks import embed_log_entry

    log_id = uuid.uuid4()
    entry = _make_log_entry(log_id)

    with (
        patch(
            "app.workers.embedding_tasks._load_log_entry",
            new=AsyncMock(return_value=entry),
        ),
        patch(
            "app.workers.embedding_tasks.decrypt_content",
            return_value="Some log content",
        ),
        patch(
            "app.workers.embedding_tasks.generate_embedding",
            side_effect=RuntimeError("Qdrant inference unavailable"),
        ),
        patch(
            "app.workers.embedding_tasks._set_embedding_status",
            new=AsyncMock(),
        ),
        # Patch the task's retry method so we can verify it's called
        patch.object(embed_log_entry, "retry", side_effect=Retry()) as mock_retry,
    ):
        with pytest.raises(Retry):
            embed_log_entry(str(log_id))

    mock_retry.assert_called_once()
    _, retry_kwargs = mock_retry.call_args
    assert "exc" in retry_kwargs
    assert "countdown" in retry_kwargs


def test_embed_log_entry_max_retries_sets_failed() -> None:
    """Sets embedding_status='failed' when max retries are exhausted."""
    from app.workers.embedding_tasks import embed_log_entry

    log_id = uuid.uuid4()
    entry = _make_log_entry(log_id)

    with (
        patch(
            "app.workers.embedding_tasks._load_log_entry",
            new=AsyncMock(return_value=entry),
        ),
        patch(
            "app.workers.embedding_tasks.decrypt_content",
            return_value="Some log content",
        ),
        patch(
            "app.workers.embedding_tasks.generate_embedding",
            side_effect=RuntimeError("Qdrant inference unavailable"),
        ),
        patch(
            "app.workers.embedding_tasks._set_embedding_status",
            new=AsyncMock(),
        ) as mock_status,
        # Retry raises MaxRetriesExceededError — task should catch and set 'failed'
        patch.object(
            embed_log_entry,
            "retry",
            side_effect=MaxRetriesExceededError(),
        ),
    ):
        embed_log_entry(str(log_id))

    mock_status.assert_called_with(log_id, "failed")


# ── delete_log_embedding ──────────────────────────────────────────────────


def test_delete_log_embedding_success() -> None:
    """Happy path: deletes the Qdrant vector."""
    from app.workers.embedding_tasks import delete_log_embedding

    log_id = uuid.uuid4()

    with patch(
        "app.workers.embedding_tasks.delete_log_vector",
        new=AsyncMock(),
    ) as mock_delete:
        delete_log_embedding(str(log_id))

    mock_delete.assert_called_once_with(log_id)


def test_delete_log_embedding_retries_on_failure() -> None:
    """Calls task.retry() when Qdrant delete raises an exception."""
    from app.workers.embedding_tasks import delete_log_embedding

    with (
        patch(
            "app.workers.embedding_tasks.delete_log_vector",
            new=AsyncMock(side_effect=RuntimeError("Qdrant connection error")),
        ),
        patch.object(
            delete_log_embedding, "retry", side_effect=Retry()
        ) as mock_retry,
    ):
        with pytest.raises(Retry):
            delete_log_embedding(str(uuid.uuid4()))

    mock_retry.assert_called_once()


# ── send_reset_password_email ─────────────────────────────────────────────


def test_send_reset_email_success() -> None:
    """Happy path: sends SMTP email when credentials are configured."""
    from app.workers.email_tasks import send_reset_password_email

    with (
        patch("app.workers.email_tasks.settings") as mock_settings,
        patch("app.workers.email_tasks.smtplib.SMTP") as mock_smtp_cls,
    ):
        mock_settings.SMTP_USER = "noreply@example.com"
        mock_settings.SMTP_PASSWORD = "secret"
        mock_settings.SMTP_HOST = "smtp.example.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.FRONTEND_URL = "https://app.mylogmate.com"

        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        send_reset_password_email("user@example.com", "fake-reset-token")

    mock_server.sendmail.assert_called_once()


def test_send_reset_email_skips_when_no_credentials() -> None:
    """Skips silently when SMTP credentials are not configured."""
    from app.workers.email_tasks import send_reset_password_email

    with (
        patch("app.workers.email_tasks.settings") as mock_settings,
        patch("app.workers.email_tasks.smtplib.SMTP") as mock_smtp_cls,
    ):
        mock_settings.SMTP_USER = ""
        mock_settings.SMTP_PASSWORD = ""

        send_reset_password_email("user@example.com", "fake-reset-token")

    mock_smtp_cls.assert_not_called()


def test_send_reset_email_retries_on_smtp_error() -> None:
    """Calls task.retry() on SMTP failure."""
    import smtplib

    from app.workers.email_tasks import send_reset_password_email

    with (
        patch("app.workers.email_tasks.settings") as mock_settings,
        patch("app.workers.email_tasks.smtplib.SMTP") as mock_smtp_cls,
        patch.object(
            send_reset_password_email, "retry", side_effect=Retry()
        ) as mock_retry,
    ):
        mock_settings.SMTP_USER = "noreply@example.com"
        mock_settings.SMTP_PASSWORD = "secret"
        mock_settings.SMTP_HOST = "smtp.example.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.FRONTEND_URL = "https://app.mylogmate.com"

        mock_smtp_cls.return_value.__enter__ = MagicMock(
            side_effect=smtplib.SMTPException("Connection refused")
        )
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        with pytest.raises(Retry):
            send_reset_password_email("user@example.com", "fake-reset-token")

    mock_retry.assert_called_once()
