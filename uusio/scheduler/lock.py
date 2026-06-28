"""PostgreSQL advisory lock for distributed job execution.

Prevents duplicate scheduler runs when multiple ECS tasks are running
simultaneously (during deployments or if auto-scaling is ever enabled).

Usage:
    async with pg_advisory_lock(session_factory, lock_id=1234) as acquired:
        if not acquired:
            return  # another instance is already running this job
        # do work here
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

# Stable numeric IDs for each scheduled job
LOCK_DEADLINE_CHECK    = 1001
LOCK_REGULATION_FETCH  = 1002
LOCK_MONTHLY_INVOICES  = 1003
LOCK_ANNUAL_INVOICES   = 1004
LOCK_AUTO_SUBMIT       = 1005


@asynccontextmanager
async def pg_advisory_lock(
    session_factory: async_sessionmaker[AsyncSession],
    lock_id: int,
):
    """Try to acquire a PostgreSQL session-level advisory lock.

    Yields True if the lock was acquired, False if another process holds it.
    The lock is released automatically when the session closes.
    """
    async with session_factory() as session:
        row = await session.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": lock_id},
        )
        acquired: bool = row.scalar()
        if not acquired:
            logger.info("Advisory lock %d already held — skipping job", lock_id)
        try:
            yield acquired
        finally:
            if acquired:
                await session.execute(
                    text("SELECT pg_advisory_unlock(:lock_id)"),
                    {"lock_id": lock_id},
                )
