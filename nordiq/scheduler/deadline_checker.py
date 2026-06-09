"""Deadline checking logic — queries DB and sends warning emails.

Called by the APScheduler job once per day. For each reporting deadline in the
epr_reporting_deadlines table, checks if today is exactly 30, 14, 7, or 1 day(s)
before the submission_deadline. When a threshold is crossed, all active users of
every active customer that has not yet submitted for that deadline receive an email.

Design decisions:
- Threshold check uses equality (==) not <=, so each warning is sent exactly once.
  A daily schedule means no duplicates.
- A customer is "not yet submitted" for a deadline if they have no EPRObligation
  with status=SUBMITTED whose period matches.
- Per-row error isolation: a failure for one customer or user never aborts the rest.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nordiq.models.customer import Customer
from nordiq.models.enums import ObligationStatus
from nordiq.models.obligation import EPRObligation, ReportingDeadline
from nordiq.models.user import User
from nordiq.notifications.email import send_deadline_warning

logger = logging.getLogger(__name__)

WARNING_THRESHOLDS = (30, 14, 7, 1)


async def check_upcoming_deadlines(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Main entry point called by the scheduler job."""
    today = date.today()
    logger.info("Running deadline check for %s", today)

    async with session_factory() as db:
        deadlines = await _load_deadlines(db, today)
        if not deadlines:
            logger.debug("No upcoming deadlines to check today")
            return

        for deadline in deadlines:
            days_left = (deadline.submission_deadline - today).days
            if days_left not in WARNING_THRESHOLDS:
                continue

            logger.info(
                "Deadline %s/%s due %s — %d days remaining, sending warnings",
                deadline.country_code, deadline.product_category,
                deadline.submission_deadline, days_left,
            )
            await _notify_customers_for_deadline(db, deadline, days_left)


async def _load_deadlines(db: AsyncSession, today: date) -> list[ReportingDeadline]:
    horizon = today + timedelta(days=31)
    result = await db.execute(
        select(ReportingDeadline).where(
            ReportingDeadline.submission_deadline >= today,
            ReportingDeadline.submission_deadline <= horizon,
        )
    )
    return result.scalars().all()


async def _notify_customers_for_deadline(
    db: AsyncSession,
    deadline: ReportingDeadline,
    days_remaining: int,
) -> None:
    customers_result = await db.execute(
        select(Customer).where(Customer.is_active == True)  # noqa: E712
    )
    customers = customers_result.scalars().all()

    for customer in customers:
        try:
            already_submitted = await _customer_has_submitted(db, customer.id, deadline)
            if already_submitted:
                logger.debug(
                    "Customer %s already submitted %s/%s — skipping",
                    customer.id, deadline.country_code, deadline.product_category,
                )
                continue
            await _send_warnings_to_customer_users(db, customer, deadline, days_remaining)
        except Exception as exc:
            logger.error(
                "Error processing deadline warnings for customer %s: %s", customer.id, exc
            )


async def _customer_has_submitted(
    db: AsyncSession,
    customer_id,
    deadline: ReportingDeadline,
) -> bool:
    result = await db.execute(
        select(EPRObligation).where(
            EPRObligation.customer_id == customer_id,
            EPRObligation.country_code == deadline.country_code,
            EPRObligation.product_category == deadline.product_category,
            EPRObligation.reporting_period_start == deadline.reporting_period_start,
            EPRObligation.reporting_period_end == deadline.reporting_period_end,
            EPRObligation.status == ObligationStatus.SUBMITTED,
        )
    )
    return result.scalar_one_or_none() is not None


async def _send_warnings_to_customer_users(
    db: AsyncSession,
    customer: Customer,
    deadline: ReportingDeadline,
    days_remaining: int,
) -> None:
    users_result = await db.execute(
        select(User).where(
            User.customer_id == customer.id,
            User.is_active == True,  # noqa: E712
        )
    )
    users = users_result.scalars().all()

    if not users:
        logger.debug("No active users for customer %s — skipping", customer.id)
        return

    sent = 0
    for user in users:
        ok = await send_deadline_warning(
            recipient_email=user.email,
            recipient_name=user.full_name or user.email,
            customer_name=customer.name,
            country_code=deadline.country_code,
            product_category=deadline.product_category,
            reporting_period_start=str(deadline.reporting_period_start),
            reporting_period_end=str(deadline.reporting_period_end),
            submission_deadline=str(deadline.submission_deadline),
            days_remaining=days_remaining,
            pro_id=deadline.pro_id,
        )
        if ok:
            sent += 1

    logger.info(
        "Sent %d/%d deadline warnings for customer %s (%s/%s due %s)",
        sent, len(users), customer.id,
        deadline.country_code, deadline.product_category, deadline.submission_deadline,
    )
