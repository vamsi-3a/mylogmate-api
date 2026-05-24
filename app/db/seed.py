"""Database seeder — sample templates and admin user.

Run via: make seed  (which calls: python -m app.db.seed)

Idempotent: safe to run multiple times. Existing samples are skipped (no duplicates).
"""

from __future__ import annotations

import asyncio
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.db.models.template import Template
from app.db.models.user import User
from app.db.session import AsyncSessionLocal

logger = structlog.get_logger()

# ── Sample templates ──────────────────────────────────────────────────────

SAMPLE_TEMPLATES: list[dict[str, str]] = [
    # Software Engineer
    {
        "name": "Daily standup",
        "category": "software_engineer",
        "content": (
            "**Yesterday:** \n"
            "- \n\n"
            "**Today:** \n"
            "- \n\n"
            "**Blockers:** \n"
            "- None"
        ),
    },
    {
        "name": "PR review session",
        "category": "software_engineer",
        "content": (
            "**PRs reviewed:** \n"
            "- \n\n"
            "**Key feedback given:** \n"
            "- \n\n"
            "**PRs merged:** \n"
            "- "
        ),
    },
    {
        "name": "Bug fix log",
        "category": "software_engineer",
        "content": (
            "**Bug:** \n\n"
            "**Root cause:** \n\n"
            "**Fix applied:** \n\n"
            "**Tests added:** \n"
            "- "
        ),
    },
    {
        "name": "Feature delivery",
        "category": "software_engineer",
        "content": (
            "**Feature:** \n\n"
            "**Delivered:** \n"
            "- \n\n"
            "**Impact:** \n\n"
            "**Follow-up:** \n"
            "- "
        ),
    },
    # Engineering Manager
    {
        "name": "Weekly 1:1",
        "category": "engineering_manager",
        "content": (
            "**With:** \n\n"
            "**Topics discussed:** \n"
            "- \n\n"
            "**Action items:** \n"
            "- \n\n"
            "**Their mood / engagement:** "
        ),
    },
    {
        "name": "Team health check",
        "category": "engineering_manager",
        "content": (
            "**Sprint velocity:** \n\n"
            "**Blockers removed this week:** \n"
            "- \n\n"
            "**Risks / concerns:** \n"
            "- \n\n"
            "**Shoutouts:** \n"
            "- "
        ),
    },
    {
        "name": "Hiring note",
        "category": "engineering_manager",
        "content": (
            "**Candidate:** \n"
            "**Role:** \n"
            "**Round:** \n\n"
            "**Strengths:** \n"
            "- \n\n"
            "**Concerns:** \n"
            "- \n\n"
            "**Decision:** "
        ),
    },
    # General
    {
        "name": "Weekly summary",
        "category": "general",
        "content": (
            "**Highlights:** \n"
            "- \n\n"
            "**Challenges:** \n"
            "- \n\n"
            "**Learnings:** \n"
            "- \n\n"
            "**Next week focus:** \n"
            "- "
        ),
    },
    {
        "name": "Incident log",
        "category": "general",
        "content": (
            "**Incident:** \n"
            "**Severity:** P\n"
            "**Duration:** \n\n"
            "**Timeline:** \n"
            "- \n\n"
            "**Root cause:** \n\n"
            "**Remediation:** \n"
            "- "
        ),
    },
    {
        "name": "Meeting notes",
        "category": "general",
        "content": (
            "**Meeting:** \n"
            "**Attendees:** \n\n"
            "**Decisions made:** \n"
            "- \n\n"
            "**Action items:** \n"
            "- "
        ),
    },
]


# ── Admin user ────────────────────────────────────────────────────────────


async def _seed_admin(db_session: AsyncSession) -> None:
    """Create the admin user if it doesn't already exist."""
    admin_email = settings.ADMIN_EMAIL
    if not admin_email:
        logger.info("seed_admin_skipped", reason="ADMIN_EMAIL not set")
        return

    result = await db_session.execute(
        select(User).where(User.email == admin_email)
    )
    if result.scalar_one_or_none() is not None:
        logger.info("seed_admin_skipped", reason="already exists", email=admin_email)
        return

    admin_password = settings.ADMIN_PASSWORD
    if not admin_password:
        logger.warning("seed_admin_skipped", reason="ADMIN_PASSWORD not set")
        return

    admin = User(
        id=uuid.uuid4(),
        email=admin_email,
        username="admin",
        password_hash=hash_password(admin_password),
        is_active=True,
        is_admin=True,
        auth_provider="local",
    )
    db_session.add(admin)
    await db_session.commit()
    logger.info("seed_admin_created", email=admin_email)


# ── Sample templates ──────────────────────────────────────────────────────


async def _seed_templates(db_session: AsyncSession) -> None:
    """Insert sample templates that don't already exist (matched by name)."""
    result = await db_session.execute(
        select(Template.name).where(Template.is_sample.is_(True))
    )
    existing_names: set[str] = set(result.scalars().all())

    new_templates = [
        Template(
            id=uuid.uuid4(),
            user_id=None,
            name=t["name"],
            content=t["content"],
            is_sample=True,
            category=t["category"],
        )
        for t in SAMPLE_TEMPLATES
        if t["name"] not in existing_names
    ]

    if new_templates:
        db_session.add_all(new_templates)
        await db_session.commit()
        logger.info("seed_templates_created", count=len(new_templates))
    else:
        logger.info("seed_templates_skipped", reason="all already exist")


# ── Entry point ───────────────────────────────────────────────────────────


async def run_seed() -> None:
    """Run all seeders."""
    async with AsyncSessionLocal() as session:
        await _seed_admin(session)
        await _seed_templates(session)
    logger.info("seed_complete")


if __name__ == "__main__":
    from app.core.logging import setup_logging

    setup_logging(debug=True)
    asyncio.run(run_seed())
