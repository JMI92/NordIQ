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
from uusio.scheduler.regulation_monitor import fetch_regulation_updates
from uusio.scheduler.invoice_generator import generate_monthly_invoices, generate_annual_invoices
from uusio.scheduler.auto_submitter import auto_submit_reports
from uusio.scheduler.lock import (
    pg_advisory_lock,
    LOCK_DEADLINE_CHECK, LOCK_REGULATION_FETCH,
    LOCK_MONTHLY_INVOICES, LOCK_ANNUAL_INVOICES, LOCK_AUTO_SUBMIT,
)

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _locked(fn, session_factory, lock_id: int) -> None:
    async with pg_advisory_lock(session_factory, lock_id) as acquired:
        if acquired:
            await fn(session_factory)


def setup_scheduler(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIOScheduler:
    """Create, configure, and start the scheduler."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        logger.warning("Scheduler already running — skipping setup")
        return _scheduler

    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        _locked, args=[check_upcoming_deadlines, session_factory, LOCK_DEADLINE_CHECK],
        trigger=CronTrigger(hour=8, minute=0, timezone="UTC"),
        id="deadline_check", name="Daily EPR deadline warning check",
        replace_existing=True, misfire_grace_time=3600,
    )

    scheduler.add_job(
        _locked, args=[fetch_regulation_updates, session_factory, LOCK_REGULATION_FETCH],
        trigger=CronTrigger(day_of_week="sun", hour=6, minute=0, timezone="UTC"),
        id="regulation_monitor", name="Weekly EPR regulation update fetch",
        replace_existing=True, misfire_grace_time=3600,
    )

    scheduler.add_job(
        _locked, args=[generate_monthly_invoices, session_factory, LOCK_MONTHLY_INVOICES],
        trigger=CronTrigger(day=1, hour=7, minute=0, timezone="UTC"),
        id="monthly_invoices", name="Monthly material fee invoice generation",
        replace_existing=True, misfire_grace_time=3600,
    )

    scheduler.add_job(
        _locked, args=[generate_annual_invoices, session_factory, LOCK_ANNUAL_INVOICES],
        trigger=CronTrigger(month=1, day=1, hour=7, minute=30, timezone="UTC"),
        id="annual_invoices", name="Annual PRO membership fee invoice generation",
        replace_existing=True, misfire_grace_time=3600,
    )

    scheduler.add_job(
        _locked, args=[auto_submit_reports, session_factory, LOCK_AUTO_SUBMIT],
        trigger=CronTrigger(hour=9, minute=0, timezone="UTC"),
        id="auto_submit_reports", name="Daily automatic EPR report submission to PROs",
        replace_existing=True, misfire_grace_time=3600,
    )

    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "APScheduler started — deadline_check at 08:00 UTC daily, "
        "regulation_monitor at 06:00 UTC Sundays"
    )
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
