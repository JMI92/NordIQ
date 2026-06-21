"""EPR calculation endpoints — run calculations, list obligations, finalise."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from uusio.api.dependencies import get_current_user
from uusio.calculators.base import ReportingPeriod
from uusio.calculators.nordic.packaging import RateEntry, RateSet
from uusio.calculators.registry import get_calculator_class
from uusio.core.database import get_db
from uusio.ingestion.base import NormalizedProductData
from uusio.models.enums import (
    DataRecordSource,
    MaterialType,
    ObligationStatus,
    ProductCategory,
)
from uusio.models.obligation import EPRObligation, EPRRate
from uusio.models.product import Product, ProductWeight
from uusio.models.user import User

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class RunCalculationRequest(BaseModel):
    country_code: str
    product_category: ProductCategory
    period_start: date
    period_end: date


class ObligationResponse(BaseModel):
    id: uuid.UUID
    country_code: str
    pro_id: str
    product_category: str
    period_start: date
    period_end: date
    total_weight_kg: str
    fee_amount: str
    currency: str
    status: str
    calculated_at: datetime | None
    calculation_snapshot: dict | None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _load_rate_set(
    db: AsyncSession,
    country_code: str,
    product_category: ProductCategory,
    as_of: date,
) -> RateSet:
    """Fetch the active EPR rates from the database and return a RateSet."""
    stmt = select(EPRRate).where(
        EPRRate.country_code == country_code.upper(),
        EPRRate.product_category == product_category,
        EPRRate.valid_from <= as_of,
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    # Keep only the most-recent rate per material (highest valid_from)
    by_material: dict[str, EPRRate] = {}
    for row in rows:
        mt = row.material_type
        if mt not in by_material or row.valid_from > by_material[mt].valid_from:
            by_material[mt] = row

    # Filter out expired rates (valid_to is set and < as_of)
    active = {
        mt: r for mt, r in by_material.items()
        if r.valid_to is None or r.valid_to >= as_of
    }

    if not active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"No EPR rates found for {country_code.upper()} / "
                f"{product_category} as of {as_of}. "
                "Please seed the epr_rates table first."
            ),
        )

    # All rates for the same country/category share the same currency
    sample = next(iter(active.values()))
    rates = {
        mt: RateEntry(
            rate_per_kg=Decimal(str(r.rate_per_kg)),
            eco_modulation_factor=Decimal(str(r.eco_modulation_factor)) if r.eco_modulation_factor is not None else Decimal("1.0"),
            is_sup_surcharge=bool(r.is_sup_surcharge) if r.is_sup_surcharge is not None else False,
            packaging_stream=r.packaging_stream,
        )
        for mt, r in active.items()
    }
    fixed_annual_fee = max(
        (Decimal(str(r.fixed_annual_fee_eur)) for r in active.values() if r.fixed_annual_fee_eur is not None),
        default=Decimal("0"),
    )

    return RateSet(
        country_code=country_code.upper(),
        product_category=product_category,
        currency=sample.currency,
        rates=rates,
        valid_from=min(r.valid_from for r in active.values()),
        valid_to=None,
        regulation_reference=sample.regulation_reference or "",
        fixed_annual_fee_eur=fixed_annual_fee,
    )


async def _load_products(
    db: AsyncSession,
    customer_id: uuid.UUID,
    product_category: ProductCategory,
    period_start: date,
    period_end: date,
) -> list[NormalizedProductData]:
    """Load all in-scope product weight records for the customer / category / period."""
    stmt = (
        select(ProductWeight, Product)
        .join(Product, ProductWeight.product_id == Product.id)
        .where(
            ProductWeight.customer_id == customer_id,
            Product.product_category == product_category,
            # overlap: weight period overlaps with requested period
            ProductWeight.reporting_period_start <= period_end,
            ProductWeight.reporting_period_end >= period_start,
        )
    )
    result = await db.execute(stmt)
    rows = result.all()

    records = []
    for weight, product in rows:
        records.append(
            NormalizedProductData(
                external_product_id=product.external_product_id,
                description=product.description,
                product_category=ProductCategory(product.product_category),
                weight_kg=float(weight.weight_kg),
                material_type=MaterialType(weight.material_type),
                reporting_period_start=weight.reporting_period_start,
                reporting_period_end=weight.reporting_period_end,
                source=DataRecordSource(weight.source),
                raw_record={},
            )
        )
    return records


def _obligation_to_response(ob: EPRObligation) -> ObligationResponse:
    return ObligationResponse(
        id=ob.id,
        country_code=ob.country_code,
        pro_id=ob.pro_id,
        product_category=ob.product_category,
        period_start=ob.reporting_period_start,
        period_end=ob.reporting_period_end,
        total_weight_kg=str(ob.total_weight_kg),
        fee_amount=str(ob.fee_amount),
        currency=ob.currency,
        status=ob.status,
        calculated_at=ob.calculated_at,
        calculation_snapshot=ob.calculation_snapshot,
    )


async def _get_owned_obligation(
    obligation_id: uuid.UUID,
    customer_id: uuid.UUID,
    db: AsyncSession,
) -> EPRObligation:
    result = await db.execute(
        select(EPRObligation).where(
            EPRObligation.id == obligation_id,
            EPRObligation.customer_id == customer_id,
        )
    )
    ob = result.scalar_one_or_none()
    if ob is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obligation not found")
    return ob


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=list[ObligationResponse])
async def list_obligations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List all EPR obligations for the authenticated customer."""
    result = await db.execute(
        select(EPRObligation)
        .where(EPRObligation.customer_id == current_user.customer_id)
        .order_by(EPRObligation.created_at.desc())
    )
    obligations = result.scalars().all()
    return [_obligation_to_response(ob) for ob in obligations]


@router.post("", response_model=ObligationResponse, status_code=status.HTTP_201_CREATED)
async def run_calculation(
    body: RunCalculationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Run an EPR calculation and persist the obligation.

    If an obligation with the same (customer, country, category, period) already
    exists in DRAFT status it is recalculated in place (idempotent).
    """
    country = body.country_code.upper()
    period = ReportingPeriod(start=body.period_start, end=body.period_end)

    # Load rates from DB
    rate_set = await _load_rate_set(db, country, body.product_category, body.period_end)

    # Load products
    products = await _load_products(
        db, current_user.customer_id, body.product_category,
        body.period_start, body.period_end,
    )

    # Run calculator
    calculator_class = get_calculator_class(country, body.product_category)
    calculator = calculator_class(rate_set)
    obligation_result = calculator.calculate(products, period)

    # Upsert: update existing DRAFT or create new
    existing_result = await db.execute(
        select(EPRObligation).where(
            EPRObligation.customer_id == current_user.customer_id,
            EPRObligation.country_code == country,
            EPRObligation.product_category == body.product_category,
            EPRObligation.reporting_period_start == body.period_start,
            EPRObligation.reporting_period_end == body.period_end,
            EPRObligation.status == ObligationStatus.DRAFT,
        )
    )
    ob = existing_result.scalar_one_or_none()

    if ob is None:
        ob = EPRObligation(
            customer_id=current_user.customer_id,
            country_code=country,
            pro_id=obligation_result.pro_id,
            product_category=body.product_category,
            reporting_period_start=body.period_start,
            reporting_period_end=body.period_end,
        )
        db.add(ob)

    ob.total_weight_kg = float(obligation_result.total_weight_kg)
    ob.fee_amount = float(obligation_result.fee_amount)
    ob.currency = obligation_result.currency
    ob.calculation_snapshot = obligation_result.calculation_snapshot
    ob.calculated_at = datetime.now(timezone.utc)
    ob.status = ObligationStatus.DRAFT

    await db.commit()
    await db.refresh(ob)
    return _obligation_to_response(ob)


@router.get("/{obligation_id}", response_model=ObligationResponse)
async def get_obligation(
    obligation_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ob = await _get_owned_obligation(obligation_id, current_user.customer_id, db)
    return _obligation_to_response(ob)


@router.post("/{obligation_id}/finalise", response_model=ObligationResponse)
async def finalise_obligation(
    obligation_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Transition a DRAFT obligation to FINALISED (locks it from further edits)."""
    ob = await _get_owned_obligation(obligation_id, current_user.customer_id, db)
    if ob.status != ObligationStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot finalise an obligation in status '{ob.status}'",
        )
    ob.status = ObligationStatus.FINALISED
    await db.commit()
    await db.refresh(ob)
    return _obligation_to_response(ob)


@router.delete("/{obligation_id}")
async def delete_obligation(
    obligation_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Delete a DRAFT obligation. FINALISED/SUBMITTED obligations cannot be deleted."""
    ob = await _get_owned_obligation(obligation_id, current_user.customer_id, db)
    if ob.status != ObligationStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete an obligation in status '{ob.status}'",
        )
    await db.delete(ob)
    await db.commit()
    return Response(status_code=204)
