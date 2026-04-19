"""Idempotent seed script for development/testing.

Creates a default user with a pre-set Anthropic API key if SEED_ANTHROPIC_API_KEY
is configured. Safe to re-run — skips creation if the email already exists.

Usage:
    cd backend && uv run python -m app.db.seed
"""

import asyncio
import logging

from sqlalchemy import select

from app.core.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.user import User
from app.services.auth_service import hash_password
from app.services.encryption_service import encrypt

logger = logging.getLogger(__name__)

SEED_EMAIL = "demo@idealens.dev"
SEED_NAME = "Demo User"
SEED_PASSWORD = "demo1234"


async def seed() -> None:
    settings = get_settings()
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == SEED_EMAIL))
        existing = result.scalar_one_or_none()
        if existing:
            logger.info("Seed user already exists — skipping.")
            return

        user = User(
            email=SEED_EMAIL,
            name=SEED_NAME,
            password_hash=hash_password(SEED_PASSWORD),
        )

        if settings.SEED_ANTHROPIC_API_KEY:
            user.encrypted_api_key = encrypt(settings.SEED_ANTHROPIC_API_KEY)
            logger.info("Seed user will have API key pre-set.")

        db.add(user)
        await db.commit()
        logger.info(
            "Seed user created: %s / %s",
            SEED_EMAIL,
            SEED_PASSWORD,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed())
