"""Automated invoice generation.

Monthly (1st of each month):
  - Material reporting fees based on EPR obligations for the previous month
  - Margin applied to material fees only
  - €30 service fee per invoice

Annual (1st January):
  - PRO annual membership fees for all active customer PRO registrations
  - Passed through at cost (no margin)
  - €30 service fee per invoice
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

SERVICE_FEE = Decimal("30.00")
DEFAULT_MARGIN = Decimal("12.00")
INVOICE_DUE_DAYS = 14


async def _get_margin(db: AsyncSession, pro_id: uuid.UUID) -> Decimal:
    from uusio.models.pro_pricing import MarginSettings
    today = date.today()
    row = (
        await db.execute(
            select(MarginSettings)
            .where(MarginSettings.pro_id == pro_id, MarginSettings.effective_date <= today)
            .order_by(MarginSettings.effective_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row:
        return row.margin_percentage
    row = (
        await db.execute(
            select(MarginSettings)
            .where(MarginSettings.pro_id.is_(None), MarginSettings.effective_date <= today)
            .order_by(MarginSettings.effective_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return row.margin_percentage if row else DEFAULT_MARGIN


async def _next_invoice_number(db: AsyncSession, prefix: str) -> str:
    from sqlalchemy import func
    from uusio.models.billing import Invoice
    count = (await db.execute(select(func.count()).select_from(Invoice))).scalar() or 0
    return f"{prefix}-{count + 1:05d}"


async def generate_monthly_invoices(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Generate monthly material fee invoices for all customers with obligations last month."""
    from uusio.models.billing import Invoice
    from uusio.models.customer import Customer
    from uusio.models.obligation import EPRObligation
    from uusio.models.pro_pricing import PRoPricing
    from uusio.models.pro_registry import PROOrganisation

    today = date.today()
    # Previous month
    first_this_month = today.replace(day=1)
    last_month_end = first_this_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    async with session_factory() as db:
        customers = (await db.execute(select(Customer).where(Customer.is_active == True))).scalars().all()  # noqa: E712

        for customer in customers:
            obligations = (
                await db.execute(
                    select(EPRObligation).where(
                        EPRObligation.customer_id == customer.id,
                        EPRObligation.reporting_period_start >= last_month_start,
                        EPRObligation.reporting_period_end <= last_month_end,
                        EPRObligation.status == "calculated",
                    )
                )
            ).scalars().all()

            if not obligations:
                continue

            line_items = []
            total = Decimal("0.00")

            for obl in obligations:
                pro = (await db.execute(select(PROOrganisation).where(PROOrganisation.id == obl.pro_id))).scalar_one_or_none()
                if not pro:
                    continue

                # Find material pricing for this PRO + product_category (waste_stream)
                pricing = (
                    await db.execute(
                        select(PRoPricing).where(
                            PRoPricing.pro_id == obl.pro_id,
                            PRoPricing.waste_stream == obl.product_category,
                            PRoPricing.fee_type == "material",
                            PRoPricing.is_active == True,  # noqa: E712
                            PRoPricing.effective_date <= today,
                        ).order_by(PRoPricing.effective_date.desc()).limit(1)
                    )
                ).scalar_one_or_none()

                if not pricing:
                    logger.warning("No material pricing for PRO %s / %s — skipping obligation %s", obl.pro_id, obl.product_category, obl.id)
                    continue

                margin_pct = await _get_margin(db, obl.pro_id)
                unit_price = pricing.amount * (1 + margin_pct / 100)
                line_total = unit_price * Decimal(str(obl.total_weight_kg))
                total += line_total

                line_items.append({
                    "description": f"{pro.name} – {obl.product_category} ({obl.country_code}) {last_month_start.strftime('%b %Y')}",
                    "quantity": float(obl.total_weight_kg),
                    "unit": "kg",
                    "unit_price": float(unit_price),
                    "margin_pct": float(margin_pct),
                    "total": round(float(line_total), 2),
                })

            if not line_items:
                continue

            # Service fee line
            line_items.append({
                "description": "Uusio service fee",
                "quantity": 1,
                "unit": "invoice",
                "unit_price": float(SERVICE_FEE),
                "margin_pct": None,
                "total": float(SERVICE_FEE),
            })
            total += SERVICE_FEE

            invoice_number = await _next_invoice_number(db, "USO-M")
            due = today + timedelta(days=INVOICE_DUE_DAYS)

            inv = Invoice(
                customer_id=customer.id,
                invoice_number=invoice_number,
                invoice_type="monthly",
                amount=total.quantize(Decimal("0.01")),
                service_fee=SERVICE_FEE,
                currency="EUR",
                status="draft",
                period_start=last_month_start,
                period_end=last_month_end,
                due_date=due,
                line_items=line_items,
            )
            db.add(inv)
            logger.info("Generated monthly invoice %s for customer %s: %.2f EUR", invoice_number, customer.id, total)

        await db.commit()


async def generate_annual_invoices(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Generate annual PRO membership fee invoices for all customers (run 1 Jan)."""
    from uusio.models.billing import Invoice
    from uusio.models.customer import Customer
    from uusio.models.pro_pricing import PRoPricing
    from uusio.models.pro_registry import CustomerPRORegistration, PROOrganisation

    today = date.today()
    year = today.year

    async with session_factory() as db:
        customers = (await db.execute(select(Customer).where(Customer.is_active == True))).scalars().all()  # noqa: E712

        for customer in customers:
            registrations = (
                await db.execute(
                    select(CustomerPRORegistration).where(
                        CustomerPRORegistration.customer_id == customer.id,
                        CustomerPRORegistration.status == "active",
                    )
                )
            ).scalars().all()

            if not registrations:
                continue

            line_items = []
            total = Decimal("0.00")

            for reg in registrations:
                pro = (await db.execute(select(PROOrganisation).where(PROOrganisation.id == reg.pro_id))).scalar_one_or_none()
                if not pro:
                    continue

                streams = reg.material_categories or []
                for stream in streams:
                    pricing = (
                        await db.execute(
                            select(PRoPricing).where(
                                PRoPricing.pro_id == reg.pro_id,
                                PRoPricing.waste_stream == stream,
                                PRoPricing.fee_type == "annual",
                                PRoPricing.is_active == True,  # noqa: E712
                                PRoPricing.effective_date <= today,
                            ).order_by(PRoPricing.effective_date.desc()).limit(1)
                        )
                    ).scalar_one_or_none()

                    if not pricing:
                        continue

                    line_items.append({
                        "description": f"{pro.name} – {stream} annual fee {year}",
                        "quantity": 1,
                        "unit": "year",
                        "unit_price": float(pricing.amount),
                        "margin_pct": None,
                        "total": float(pricing.amount),
                    })
                    total += pricing.amount

            if not line_items:
                continue

            line_items.append({
                "description": "Uusio service fee",
                "quantity": 1,
                "unit": "invoice",
                "unit_price": float(SERVICE_FEE),
                "margin_pct": None,
                "total": float(SERVICE_FEE),
            })
            total += SERVICE_FEE

            invoice_number = await _next_invoice_number(db, f"USO-A{year}")
            due = today + timedelta(days=INVOICE_DUE_DAYS)

            inv = Invoice(
                customer_id=customer.id,
                invoice_number=invoice_number,
                invoice_type="annual",
                amount=total.quantize(Decimal("0.01")),
                service_fee=SERVICE_FEE,
                currency="EUR",
                status="draft",
                period_start=date(year, 1, 1),
                period_end=date(year, 12, 31),
                due_date=due,
                line_items=line_items,
            )
            db.add(inv)
            logger.info("Generated annual invoice %s for customer %s: %.2f EUR", invoice_number, customer.id, total)

        await db.commit()
