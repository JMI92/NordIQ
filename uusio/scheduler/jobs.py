"""APScheduler setup — wires the deadline checker into an AsyncIOScheduler.

The scheduler runs inside the FastAPI event loop (AsyncIOScheduler) so that
async DB sessions and async email sends work without an extra thread pool.

Call setup_scheduler() from the FastAPI lifespan context, passing the
SQLAlchemy async_sessionmaker.  Call shutdown_scheduler() on app shutdown.

Schedule:
  - deadline_check: daily at 08:00 UTC
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from uusio.scheduler.deadline_checker import check_upcoming_deadlines

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def setup_scheduler(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIOScheduler:
    """Create, configure, and start the scheduler."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        logger.warning("Scheduler already running — skipping setup")
        return _scheduler

    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        check_upcoming_deadlines,
        trigger=CronTrigger(hour=8, minute=0, timezone="UTC"),
        id="deadline_check",
        name="Daily EPR deadline warning check",
        args=[session_factory],
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.start()
    _scheduler = scheduler
    logger.info("APScheduler started — deadline_check job scheduled at 08:00 UTC daily")
    return scheduler


def shutdown_scheduler() -> None:
    """Gracefully shut down the scheduler on app shutdown."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler shut down")
    _scheduler = None


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler
