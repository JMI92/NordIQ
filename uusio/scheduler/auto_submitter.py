"""Automatic EPR report submission to PROs.

Runs daily and finds obligations that:
  - Are in "calculated" status
  - Have a submission deadline within SUBMIT_DAYS_BEFORE days
  - Belong to a PRO with submission_method = "email"

For each, it:
  1. Generates a CSV report
  2. Emails it to the PRO's submission_email
  3. Creates a PROSubmission record
  4. Updates obligation status to "submitted"

PROs with submission_method = "portal" or "manual" are flagged for
manual action but not auto-submitted.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

SUBMIT_DAYS_BEFORE = 5  # submit this many days before deadline


def _generate_csv(obligation, customer_name: str) -> tuple[bytes, str]:
    """Generate a CSV report for an obligation. Returns (content, filename)."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "customer_name", "country_code", "product_category",
        "reporting_period_start", "reporting_period_end",
        "total_weight_kg", "fee_amount", "currency",
    ])
    writer.writerow([
        customer_name,
        obligation.country_code,
        obligation.product_category,
        obligation.reporting_period_start.isoformat() if obligation.reporting_period_start else "",
        obligation.reporting_period_end.isoformat() if obligation.reporting_period_end else "",
        str(obligation.total_weight_kg),
        str(obligation.fee_amount),
        obligation.currency,
    ])

    # Material breakdown from calculation snapshot
    snapshot = obligation.calculation_snapshot or {}
    weight_by_material = snapshot.get("weight_by_material", {})
    fee_by_material = snapshot.get("fee_by_material", {})
    rates_used = snapshot.get("rates_used", {})

    if weight_by_material:
        writer.writerow([])
        writer.writerow(["material_type", "weight_kg", "rate_per_kg", "fee_amount", "currency"])
        for material, weight in weight_by_material.items():
            writer.writerow([
                material,
                weight,
                rates_used.get(material, ""),
                fee_by_material.get(material, ""),
                obligation.currency,
            ])

    content = output.getvalue().encode("utf-8")
    period = obligation.reporting_period_start.strftime("%Y%m") if obligation.reporting_period_start else "unknown"
    filename = f"epr_report_{obligation.country_code}_{obligation.product_category}_{period}.csv"
    return content, filename


async def auto_submit_reports(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Find due obligations and submit reports to PROs automatically."""
    from uusio.models.customer import Customer
    from uusio.models.obligation import EPRObligation, ReportingDeadline
    from uusio.models.pro_registry import PROOrganisation
    from uusio.models.submission import PROSubmission
    from uusio.notifications.email import send_pro_report

    today = date.today()
    cutoff = today + timedelta(days=SUBMIT_DAYS_BEFORE)

    async with session_factory() as db:
        # Find obligations that are calculated and have a deadline within cutoff
        deadlines = (
            await db.execute(
                select(ReportingDeadline).where(
                    ReportingDeadline.submission_deadline >= today,
                    ReportingDeadline.submission_deadline <= cutoff,
                )
            )
        ).scalars().all()

        for deadline in deadlines:
            # Find matching calculated obligations
            obligations = (
                await db.execute(
                    select(EPRObligation).where(
                        EPRObligation.country_code == deadline.country_code,
                        EPRObligation.product_category == deadline.product_category,
                        EPRObligation.pro_id == deadline.pro_id,
                        EPRObligation.reporting_period_start == deadline.reporting_period_start,
                        EPRObligation.reporting_period_end == deadline.reporting_period_end,
                        EPRObligation.status == "calculated",
                    )
                )
            ).scalars().all()

            for obl in obligations:
                # Check for existing submission to avoid duplicates
                existing = (
                    await db.execute(
                        select(PROSubmission).where(
                            PROSubmission.obligation_id == obl.id,
                            PROSubmission.status.in_(["sent", "confirmed"]),
                        )
                    )
                ).scalar_one_or_none()
                if existing:
                    continue

                pro = (
                    await db.execute(
                        select(PROOrganisation).where(PROOrganisation.id == obl.pro_id)
                    )
                ).scalar_one_or_none()
                if not pro:
                    logger.warning("PRO not found for obligation %s", obl.id)
                    continue

                customer = (
                    await db.execute(
                        select(Customer).where(Customer.id == obl.customer_id)
                    )
                ).scalar_one_or_none()
                if not customer:
                    continue

                method = pro.submission_method or "manual"

                if method == "email" and pro.submission_email:
                    csv_content, csv_filename = _generate_csv(obl, customer.name)
                    success = await send_pro_report(
                        pro_email=pro.submission_email,
                        pro_name=pro.name,
                        customer_name=customer.name,
                        country_code=obl.country_code,
                        product_category=str(obl.product_category),
                        period_start=obl.reporting_period_start.isoformat() if obl.reporting_period_start else "",
                        period_end=obl.reporting_period_end.isoformat() if obl.reporting_period_end else "",
                        csv_content=csv_content,
                        csv_filename=csv_filename,
                    )

                    submission = PROSubmission(
                        customer_id=obl.customer_id,
                        obligation_id=obl.id,
                        pro_id=str(obl.pro_id),
                        submission_method="email",
                        status="sent" if success else "failed",
                        report_file_path=csv_filename,
                        response_payload={"email": pro.submission_email, "success": success},
                        error_message=None if success else "SMTP send failed — see logs",
                    )
                    db.add(submission)

                    if success:
                        obl.status = "submitted"
                        logger.info(
                            "Auto-submitted report for obligation %s to %s (%s)",
                            obl.id, pro.name, pro.submission_email,
                        )
                    else:
                        logger.error(
                            "Failed to auto-submit obligation %s to %s",
                            obl.id, pro.submission_email,
                        )

                elif method in ("portal", "manual"):
                    # Flag for manual action — create pending submission
                    existing_pending = (
                        await db.execute(
                            select(PROSubmission).where(
                                PROSubmission.obligation_id == obl.id,
                                PROSubmission.status == "pending",
                            )
                        )
                    ).scalar_one_or_none()
                    if not existing_pending:
                        submission = PROSubmission(
                            customer_id=obl.customer_id,
                            obligation_id=obl.id,
                            pro_id=str(obl.pro_id),
                            submission_method=method,
                            status="pending",
                            response_payload={
                                "note": f"Manual submission required via {method}",
                                "portal_url": pro.portal_url,
                                "deadline": deadline.submission_deadline.isoformat(),
                            },
                        )
                        db.add(submission)
                        logger.info(
                            "Flagged obligation %s for manual %s submission to %s",
                            obl.id, method, pro.name,
                        )

        await db.commit()
