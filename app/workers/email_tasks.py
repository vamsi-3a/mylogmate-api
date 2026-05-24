"""Celery email tasks — transactional email sending.

Tasks:
  send_reset_password_email — sends password reset link to the user

Rules (workers.md):
  - bind=True, max_retries=3, acks_late=True
  - Exponential backoff: countdown=30 * (2 ** retry_count)
  - Use stdlib smtplib (sync, no asyncio needed for SMTP)
  - Log start, success, and failure with structlog
  - NEVER log the reset token — only log the recipient email

Settings used:
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD (from app.core.config)
"""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import structlog

from app.core.config import settings
from app.workers.celery_app import celery_app

logger = structlog.get_logger()

# ── Email builders ────────────────────────────────────────────────────────


def _build_reset_email(recipient_email: str, reset_token: str) -> MIMEMultipart:
    """Build the password reset email (plain text + HTML)."""
    # NOTE: Never log reset_token — it is a credential
    reset_url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={reset_token}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Reset your MyLogMate password"
    msg["From"] = settings.SMTP_USER
    msg["To"] = recipient_email

    plain_body = (
        f"Hi,\n\n"
        f"You requested a password reset for your MyLogMate account.\n\n"
        f"Click the link below to reset your password (expires in 15 minutes):\n"
        f"{reset_url}\n\n"
        f"If you didn't request this, you can safely ignore this email.\n\n"
        f"— MyLogMate"
    )

    html_body = f"""
    <html>
      <body style="font-family:sans-serif;color:#1a1a1a;max-width:480px;margin:0 auto">
        <h2 style="color:#2563eb">Reset your password</h2>
        <p>You requested a password reset for your MyLogMate account.</p>
        <p>
          <a href="{reset_url}"
             style="background:#2563eb;color:#fff;padding:12px 24px;border-radius:6px;
                    text-decoration:none;display:inline-block">
            Reset password
          </a>
        </p>
        <p style="color:#6b7280;font-size:13px">
          Link expires in 15 minutes.<br>
          If you didn't request this, you can safely ignore this email.
        </p>
      </body>
    </html>
    """

    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    return msg


# ── Tasks ─────────────────────────────────────────────────────────────────


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="app.workers.email_tasks.send_reset_password_email",
    queue="emails",
    max_retries=3,
    acks_late=True,
    default_retry_delay=30,
)
def send_reset_password_email(
    self: Any,
    recipient_email: str,
    reset_token: str,
) -> None:
    """Send the password reset email to the user.

    Uses SMTP_HOST/PORT/USER/PASSWORD from settings.
    Retries up to 3 times with exponential backoff on SMTP failure.

    NEVER logs the reset_token — only the recipient email.
    """
    logger.info("send_reset_email_start", recipient=recipient_email)

    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning(
            "send_reset_email_skipped",
            recipient=recipient_email,
            reason="SMTP credentials not configured",
        )
        return

    try:
        msg = _build_reset_email(recipient_email, reset_token)

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_USER, recipient_email, msg.as_string())

        logger.info("send_reset_email_success", recipient=recipient_email)

    except smtplib.SMTPException as exc:
        logger.error(
            "send_reset_email_failed",
            recipient=recipient_email,
            error=str(exc),
            attempt=self.request.retries + 1,
        )
        raise self.retry(
            exc=exc,
            countdown=30 * (2 ** self.request.retries),
        ) from exc
